"""
#Setup for debugging with VSCode 
import os
print(os.getcwd())
import KAPy
os.chdir("../..")
config=KAPy.getConfig("./config/config.yaml")  
wf=KAPy.getWorkflow(config)
varID='e_sat'
inputVars=config['secondaryVars'][varID]['inputVars']
outputVars=config['secondaryVars'][varID]['outputVars']
processorType=config['secondaryVars'][varID]['processorType']
processorPath=config['secondaryVars'][varID]['processorPath']
processorFunction=config['secondaryVars'][varID]['processorFunction']
passXarrays=config['secondaryVars'][varID]['passXarrays']
additionalArgs=config['secondaryVars'][varID]['additionalArgs']
outFile=list(wf['secondaryVars'][thisID])[0]
inFiles=wf['secondaryVars'][thisID][outFile]
from KAPy import helpers 
"""

import xarray as xr
import importlib
import os
from . import helpers


def buildDerivedVar(outFile,inFiles, inputVars,outputVars,processorType,
                    processorPath,processorFunction,passXarrays,additionalArgs,**kwargs):

    # Load input files
    if passXarrays=='True':  # Then load the paths into xarrays. Otherwise just pass the path.
        inFiles = {thisKey: helpers.readFile(thisPath) for thisKey, thisPath in inFiles.items()}

    # Now get the function to call
    if processorType == "module":
        thisModule = importlib.import_module(processorPath)
        thisFn = getattr(thisModule, processorFunction)
    elif processorType == "script":
        thisFn=helpers.getExternalFunction(processorPath,
                                            processorFunction)
    else:
        raise ValueError(f"processorType '{processorType}' is invalid.")

    # Call function
    theseArgs = {**inFiles, **additionalArgs}
    out = thisFn(**theseArgs)

    # Write the results to disk
    chunkThisWay=[min([256,16,16][i],out.shape[i]) for i in range(0,3)]
    out.name = outputVars[0]
    out.to_netcdf(outFile[0],
                encoding={outputVars[0]:{'chunksizes':chunkThisWay,
                                         'zlib': True,
                                         'complevel':1}})

