"""
import os
os.chdir("..")
os.chdir("..")
thisPath='outputs/1.primVars/pr_KA-ba_rcp26_EUR-11_CCCma-CanESM2r1i1p1_CLMcom-CCLM4-8-17_v1_day_19510101-20051231_DENMARK.pkl'
"""

import pickle
import xarray as xr
import os
import importlib


def readFile(thisPath,format=None):
    # Reads a dataset from disk, determining dynmaically whether it is
    # pickled or NetCDF based on the file extension
    if format==None:
        format = os.path.splitext(os.path.basename(thisPath))[1]
    if format == ".nc":
        #Each file should only contain one variable, but we also need
        #to handle the situation where there is CRS information stored
        #as a variable. Hence, we open as a dataset, and then proceed
        #from there
        thisDS = xr.open_dataset(thisPath,
                                    use_cftime=True)
        #Check for more than one non-CRS value
        if ('crs' in thisDS.data_vars) & (len(list(thisDS.data_vars))==2):
            thisVar=[k for k in thisDS.data_vars if k != "crs"]
            thisDat=thisDS[thisVar[0]]
        elif (len(list(thisDS.data_vars))==1):
            thisDat=thisDS[list(thisDS.data_vars)[0]]
        else:
            raise ValueError(f"{thisPath} contains more than one (non-CRS) variable. " +
                       f"The variables are {list(thisDS.data_vars)}")
    elif format == ".pkl":  # Read pickle
        with open(thisPath, "rb") as f:
            thisDat = pickle.load(f)
    else:
        raise IOError(f"Unknown file format, '{format}' inferred from: '{thisPath}'.")
    return thisDat


def timeslice(this,startYr,endYr):
    # Slice dataset
    timemin = this.time.dt.year >= int(startYr)
    timemax = this.time.dt.year <= int(endYr)
    sliced = this.sel(time=timemin & timemax)
    return sliced


def getExternalFunction(scriptPath,functionName):
    """
    Retrieves a function from an external file 

    Args:
        scriptPath (_type_): Path to the script file containing the function
        functionName (_type_): Name of the function to retrieve
    """
    thisSpec = importlib.util.spec_from_file_location("customScript", scriptPath)
    thisModule = importlib.util.module_from_spec(thisSpec)
    thisSpec.loader.exec_module(thisModule)
    thisFn = getattr(thisModule, functionName)
    return(thisFn)
