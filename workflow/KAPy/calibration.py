"""
#Setup for debugging with VS code
import os
print(os.getcwd())
import helpers as helpers
os.chdir("..")
import KAPy
os.chdir("../..")
config=KAPy.getConfig("./config/config.yaml")  
histsimFile='./outputs/1.variables/tas/tas_CORDEX_EUR-11_rcp85_IPSL-IPSL-CM5A-MR_r1i1p1_DMI-HIRHAM5_v1.nc'
refFile="./outputs/1.variables/tas/tas_KGDK_KGDK_no-expt_tas_klimagrid_2023.nc"
thisCal='tas-cal'
%matplotlib qt
import matplotlib.pyplot as plt
"""

from cdo import Cdo
import tempfile
from . import helpers

def calibrate(config,histSimFile,refFile,outFile, thisCal):
    #Setup
    calCfg=config['calibration'][thisCal]
    cdo=Cdo(tempdir='/dmidata/projects/klimaatlas/CLIM4CITIES/tmp/')

    # We choose to follow here the Xclim typology of ref / hist / sim, with the
    # assumption that the hist and sim part are contained in the same file ("histsim)")

    # Regrid histsim using CDO nearest neighbour interpolation. We initially did this
    # using the grid descriptor, but it works much better if you use the input file
    # directly, to ensure that all necessary auxiliary information is included.
    histsimNNFname=cdo.remapnn(refFile,input=histSimFile)
    histsimNN=helpers.readFile(histsimNNFname,format=".nc").compute()

    #Now import reference data - enforce loading, to avoid dask issues
    refDat=helpers.readFile(refFile).compute()

    #Truncate time slice to the common calibration period (CP). Ensure synchronisation
    #between times and grids using nearest neighbour interpolation of
    #the sim data to the obs data
    histsimNNCP=helpers.timeslice(histsimNN,
                     calCfg['calPeriodStart'],
                     calCfg['calPeriodEnd'])
    refDatCP=helpers.timeslice(refDat,
                     calCfg['calPeriodStart'],
                     calCfg['calPeriodEnd'])

    #Match calendars between observations and simulations
    #Note that here we have chosen here to align on year when converting to/from
    #a 360 day calendar. This follows the recommendation in the xarray documentaion,
    #under the assumption that we are primarily going to be working with daily data.
    #See here for details:
    #https://docs.xarray.dev/en/stable/generated/xarray.Dataset.convert_calendar.html
    histsimNNCP=histsimNNCP.convert_calendar(refDatCP.time.dt.calendar,
                                   use_cftime=True,
                                   align_on="year")                     

    #Setup mapping to methods and grouping
    cmethodsAdj={"cmethods-linear":'linear_scaling',
              "cmethods-variance":'variance_scaling',
              "cmethods-delta":"delta_method",
              "cmethods-quantile":'quantile_mapping',
              "cmethods-quantile-delta":'quantile_delta_mapping'}
    if calCfg['grouping']=="none":
        grouping="time"
    else:
        grouping="time."+calCfg['grouping']

    #Apply method
    if calCfg['method'] in cmethodsAdj.keys():
        raise ValueError('"cmethods" methods are currently disabled')
        from cmethods import adjust        #Use the adjust function from python cmethods
        res=adjust(method=cmethodsAdj[calCfg['method']],
                    obs=refDatCP,
                    simh=histsimNNCP,
                    simp=histsimNN,
                    group="time."+calCfg['grouping'],
                    **calCfg['additionalArgs'])

    elif calCfg['method']=="cmethods-detrended":
        # Distribution methods from cmethods
        from cmethods.distribution import detrended_quantile_mapping
        raise ValueError('"cmethods-detrended" method is currently not implemented')

    elif calCfg['method']=="xclim-eqm":
        #Empirical quantile mapping -----------------------------
        from xclim.sdba import EmpiricalQuantileMapping
        EQM = EmpiricalQuantileMapping.train(refDatCP, 
                                                 histsimNNCP, 
                                                 group=grouping,
                                                 **calCfg['additionalArgs'])
        res = EQM.adjust(histsimNN, extrapolation="constant", interp="nearest")

    elif calCfg['method']=="xclim-dqm":
        #Detrended quantile mapping -----------------------------
        from xclim.sdba import DetrendedQuantileMapping
        DQM = DetrendedQuantileMapping.train(refDatCP, 
                                                 histsimNNCP, 
                                                 group=grouping,
                                                 **calCfg['additionalArgs'])
        res = DQM.adjust(histsimNN, extrapolation="constant", interp="nearest")

    elif calCfg['method']=="xclim-scaling":
        #Xclim - Scaling--------------------------------
        from xclim.sdba.adjustment import Scaling
        this = Scaling.train(refDatCP, 
                                   histsimNNCP,
                                   group=grouping,
                                   **calCfg['additionalArgs'])
        res = this.adjust(histsimNN, interp="nearest")


    elif calCfg['method']=="custom":
        raise ValueError('"custom" calibration is currently not implemented')
    
    else:
        #Custom defined function
        raise ValueError(f'Unsupported calibration method "{calCfg['method']}".')


    #Finish
    res = res.transpose(*refDatCP.dims)
    res.name=calCfg['outVariable']
    res.to_netcdf(outFile[0])


