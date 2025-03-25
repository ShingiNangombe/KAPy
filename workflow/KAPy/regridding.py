"""
#Setup for debugging with a Jupyterlab console
import os
print(os.getcwd())
import helpers
os.chdir("..")
import KAPy
os.chdir("../..")
config=KAPy.getConfig("./config/config.yaml")  
wf=KAPy.getWorkflow(config)
outFile=[list(wf['regridded'].keys())[0]]
inFile=wf['regridded'][outFile[0]]
%matplotlib inline
"""

import xarray as xr
from cdo import Cdo 
import numpy as np
import scipy as sp
import xesmf as xe
from . import helpers

def regrid(config, inFile, outFile):
    # Check regridding approach is valid
    if not config["outputGrid"]["templateType"] in ["file","cdo"]:
        raise ValueError("Regridding options are currently limited to `file` or `cdo`. See documentation")

    # Setup input files
    # ------------------
    # Note that as this is an indicator file, we open it as a dataset
    thisDat = xr.open_dataset(inFile[0],
                              use_cftime=True)
    # Identify time coordinate
    if 'time' in thisDat.dims:
        tCoord='time'
    elif 'periodID' in thisDat.dims:
        tCoord='periodID'
    else:
        raise ValueError(f'Cannot find time or periodID coordinate in "{inFile[0]}".')
    
    # Fill in the NaNs before regridding, to avoid bleeding from the surroundings
    # This is a bit work - we use scipy's griddata routine for regridding
    # of irregular data, as there is not really anything corresponding in xarray unfortunately.
    # This is only necessary though if there are NaNs in the file in the first place
    if np.isnan(thisDat.indicator).any().values | np.isnan(thisDat.delta).any().values:
        for var in ['indicator','delta']:
            for tID in np.arange(thisDat[tCoord].size):
                for sID in np.arange(thisDat.seasonID.size):
                    # Extract data. Skip if all NaNs
                    d=thisDat[var].isel({tCoord:tID,"seasonID":sID})
                    if d.isnull().all().values:
                        continue
                    #Extract non-nan values
                    dDf=d.to_dataframe()
                    valuesDf=dDf[~np.isnan(dDf[var])]
                    #Perform interpolation / extrapolation
                    xVals=d[d.dims[1]].values
                    yVals=d[d.dims[0]].values
                    yGrd, xGrd = np.meshgrid(yVals, xVals, indexing='ij')
                    grd = sp.interpolate.griddata(np.array(valuesDf.index.to_list()),
                                    valuesDf[var].to_numpy(),
                                    (yGrd,xGrd),
                                    method='nearest')
                    thisDat[var].values[tID,sID]=grd

    #Setup the reference grid, either by importing the file, or generating it with CDO
    if config["outputGrid"]["templateType"] == "file":
        #Import reference file directly
        refGrd=xr.open_dataarray(config["outputGrid"]["path"])
    else:
        #Use the CDO griddes to make one
        cdo=Cdo(tempdir=config['dirs']['tempDir'])
        refGrd=cdo.const(42,config["outputGrid"]["path"],
                            returnXArray='const')

    # Apply regriddinng
    # ------------------
    #Ideally unmapped_to_nan should be True, but these causes segmentation faults
    #in xESMF v0.8.8. May be fixed in future versions. Generally this is not a problem
    #however, as we mask the output later in the process, removing any unmapped areas
    regrdr=xe.Regridder(thisDat,refGrd,
                        method=config["outputGrid"]["method"],
                        unmapped_to_nan=False)  
    
    #Do regridding
    regrdded=regrdr(thisDat,keep_attrs=True)

    #Mask output
    out=regrdded.where(~ np.isnan(refGrd),np.nan)

    #Write output
    out.to_netcdf(outFile[0])
