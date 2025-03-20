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
outFile=[list(wf['regridded'].keys())[1]]
inFile=wf['regridded'][outFile[0]]
%matplotlib inline
"""

import xarray as xr
import xesmf as xe
from . import helpers

def regrid(config, inFile, outFile):
    # Currently only works for 'cdo' regridding. Other engines such as xesmf could be supported in the future
    if not config["outputGrid"]["templateType"] == "file":
        raise ValueError("Regridding options are currently limited to `file`. See documentation")

    # Setup input file
    # Note that as this is an indicator file, we open it as a dataset
    thisDat = xr.open_dataset(inFile[0],
                              use_cftime=True)

    #Setup reference grid
    refGrd=xr.open_mfdataset(config["outputGrid"]["path"])

    #Setup regridder
    #Ideally unmapped_to_nan should be True, but these causes segmentation faults
    #in xESMF v0.8.8. May be fixed in future versions
    regrdr=xe.Regridder(thisDat,refGrd,
                        method=config["outputGrid"]["method"],
                        unmapped_to_nan=False)  
    
    #Do regridding
    out=regrdr(thisDat,keep_attrs=True)

    #Write output
    out.to_netcdf(outFile[0])
