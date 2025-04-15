"""
#Setup for debugging with VS code
import os
print(os.getcwd())
os.chdir("..")
import KAPy
import KAPy.helpers as helpers
os.chdir("../..")
config=KAPy.getConfig("./config/config.yaml")  
wf=KAPy.getWorkflow(config)
indID='i010'
outFile=list(wf['indicators'][indID])[0]
inFile=wf['indicators'][indID][outFile]
%matplotlib inline
"""

import xarray as xr
import xclim as xc
import numpy as np
import cftime
import json
import pandas as pd
from . import helpers 

def calculateIndicators(config, inFile, outFile, indID):

    # Retrieve indicator information
    thisInd = config["indicators"][indID]

    #Setup seasons
    if "all" in thisInd['seasons']:
        indSeasons=list(config["seasons"].keys())
    else:
        indSeasons = thisInd["seasons"]

    # Read the dataset object back from disk, depending on the configuration
    thisDat = helpers.readFile(inFile[0])

    #Internal function to choose and apply the indicator statistic
    def applyStat(d,thisStat,args):
        if thisStat=="mean":
            res = d.mean("time", keep_attrs=True)
        elif thisStat=="count":
            #Check input arguments
            if not (('op' in args) & ('threshold' in args)):
                raise ValueError("The 'additionalArgs' field must contain both 'op' and 'threshold' when using the 'count' statistic. ")
            try:
                num = float(args['threshold'])
            except ValueError:
                raise ValueError(f"Cannot convert 'threshold' value in 'additionalArgs' to a float. 'Threshold' string value: {args['threshold']}")
            #Do count
            comp = xc.indices.generic.compare(left=d,
                                             op=args['op'],
                                             right=float(args['threshold']))
            res=comp.groupby("time.year").sum().mean(dim="year")
        elif thisStat=="custom":
            #Use a custom function
            custFn=helpers.getExternalFunction(thisInd["customScriptPath"],
                                               thisInd["customScriptFunction"])
            res = custFn(d)  
        else:
            raise ValueError(f"Unknown indicator statistic, '{thisStat}'")
        return(res)

    # Time binning over periods
    # ----------------------------------
    if thisInd["time_binning"] == "periods":
        periodSlices = []
        for thisPeriod in config["periods"].values():
            # Slice dataset by time
            # It is possible that we end with an empty slice at this stage e.g. when
            # working with observations, but with time slices in the future. We handle
            # that case further one, as we still want empty slices returned
            datPeriod=helpers.timeslice(thisDat,thisPeriod["start"],thisPeriod["end"])

            #Loop over seasons
            seasonSlices=[]
            for thisSeason in indSeasons:
                # If datPeriod is already empty, then trying to filter by months will
                # just cause things to break. So, only filter data by season if there
                # is something to filter
                if datPeriod.time.size !=0:
                    theseMonths = config["seasons"][thisSeason]["months"]
                    datPeriodSeason = datPeriod.sel(time=np.isin(datPeriod.time.dt.month, theseMonths))
                    #Test for an empty slice
                    mtSlice=(datPeriodSeason.time.size == 0)
                else:
                    mtSlice=True

                # If there is nothing left, we want a result all the same so that we
                # can put it in the outputs. We copy the structure and populate
                # it with NaNs
                if mtSlice:
                    res = thisDat.isel(time=0,drop=True)
                    res.data[:] = np.nan
                # Else apply the operator
                else:
                    res=applyStat(datPeriodSeason,
                                thisInd["statistic"],
                                thisInd["additionalArgs"])
                # Store output
                res["seasonID"] = thisSeason
                seasonSlices.append(res)
            
            #Concatenate seasons into a dataarray and store
            outSeason= xr.concat(seasonSlices, dim='seasonID')
            outSeason["periodID"] = thisPeriod["id"]
            periodSlices.append(outSeason)

        # Concatenate across periods now
        dout = xr.concat(periodSlices, dim="periodID")

        #Tidy metadata
        dout.periodID.attrs["name"] = "periodID"
        dout.seasonID.attrs["name"] = "seasonID"

    # Time binning by years
    # ----------------------------
    elif thisInd["time_binning"] in ["years"]:
        #Loop over seasons
        seasonTimeseries=[]
        for thisSeason in indSeasons:
            #Filter data by season
            theseMonths = config["seasons"][thisSeason]["months"]
            datSeason = thisDat.sel(time=np.isin(thisDat.time.dt.month, theseMonths))

            # Then group by time. Could consider using groupby as an alternative
            datGroupped = datSeason.resample(time="YS")
        
            # Apply the operator
            res=applyStat(datGroupped,
                            thisInd["statistic"],
                            thisInd["additionalArgs"])
                            # Store output
            #Store the results
            res["seasonID"] = thisSeason
            seasonTimeseries.append(res)

        # Concatenate across periods now
        dout = xr.concat(seasonTimeseries, dim="seasonID")
        dout=dout.transpose('time','seasonID',...)

        #Tidy metadata
        dout.seasonID.attrs["name"] = "seasonID"

        # Round time to the first day of the year. This ensures that everything
        # has an identical datetime, regardless of the calendar being used.
        # Kudpos to ChatGPT for this little work around
        # Note that we need to ensure cftime representation, for runs that
        # go out paste 2262
        dout["time"] = [cftime.DatetimeGregorian(x.dt.strftime("%Y"),
                                                 x.dt.strftime("%m"),
                                                 1)
                                                for x in dout.time]
    else:
        raise ValueError(f"Unknown time_binning method, '{thisInd["time_binning"]}'.")


    # Calculation of changes
    # ------------------------
    # First we need the values for the reference period. That's easy for
    # period binning, but we need to calculate it for annual binning
    if thisInd["time_binning"] == "periods":
        # We use the first periodID as the reference here
        ref=dout.isel(periodID=0)
    elif thisInd["time_binning"] in ["years"]:
        # Again use the first time period, but average
        refPeriod=list(config["periods"].values())[0]
        refDat=helpers.timeslice(dout,refPeriod["start"],refPeriod["end"])
        ref=refDat.mean(dim='time')
    else:
        raise ValueError(f"Unknown time_binning method, '{thisInd["time_binning"]}'.")

    #Calculate change
    if thisInd['deltaType']=='subtract':
        deltaOut=dout-ref
    elif thisInd['deltaType']=='divide':
        deltaOut=dout/ref
    else:
        raise ValueError(f"Unknown deltaType method, '{thisInd["deltaType"]}'.")
    deltaOut.attrs['deltaType']=thisInd['deltaType']

    # Polish final product
    # ----------------------
    #Merge into one object. Add attributes
    ds=xr.Dataset({'indicator':dout,'delta':deltaOut})
    ds.attrs = {}
    for thiskey in thisInd.keys():
        if thiskey != "files":
            ds.attrs[thiskey] = str(thisInd[thiskey])
    ds.attrs["seasonID_dict"] = json.dumps(config['seasons'])
    if thisInd["time_binning"] == "periods":
        ds.attrs["periodID_dict"]= json.dumps(config['periods'])

    # Write out
    ds.to_netcdf(outFile[0])
