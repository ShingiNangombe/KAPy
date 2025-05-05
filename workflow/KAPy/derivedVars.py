"""
#Setup for debugging with VSCode 
import os
print(os.getcwd())
import KAPy
os.chdir("../..")
config=KAPy.getConfig("./config/config.yaml")  
wf=KAPy.getWorkflow(config)
thisID='e_sat'
thisVar=config['secondaryVars'][thisID]
outFile=list(wf['secondaryVars'][thisID])[0]
inFiles=wf['secondaryVars'][thisID][outFile]
from KAPy import helpers 
"""

import xarray as xr
import importlib
import os
from . import helpers


def buildDerivedVar(config, inFiles, outFile, thisVar):

    # Build the input list into a dict
    inDict = {os.path.basename(os.path.dirname(f)): f for f in inFiles}

    # Load input files
    if thisVar["passXarrays"]=='True':  # Then load the paths into xarrays. Otherwise just pass the path.
        inDict = {thisKey: helpers.readFile(thisPath) for thisKey, thisPath in inDict.items()}

    # Now get the function to call
    if thisVar["processorType"] == "module":
        thisModule = importlib.import_module(thisVar["processorPath"])
        thisFn = getattr(thisModule, thisVar["processorFunction"])
    elif thisVar["processorType"] == "script":
        thisFn=helpers.getExternalFunction(thisVar["processorPath"],
                                            thisVar["processorFunction"])
    else:
        sys.exit("Shouldn't be here")

    # Call function
    theseArgs = {**inDict, **thisVar["additionalArgs"]}
    out = thisFn(**theseArgs)

    # Write the results to disk
    out.name = thisVar["id"]
    out.to_netcdf(outFile[0],
                encoding={thisVar["id"]:{'chunksizes':[256,16,16],
                                         'zlib': True,
                                         'complevel':1}})

