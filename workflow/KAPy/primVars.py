"""
#Setup for debugging with VSCode
import os
print(os.getcwd())
os.chdir("..")
import KAPy
os.chdir("..")
os.chdir("..")
print(os.getcwd())
config=KAPy.getConfig("./config/config.yaml")  
wf=KAPy.getWorkflow(config)
inpID=next(iter(wf['primVars'].keys()))
outFile=[next(iter(wf['primVars'][inpID]))]
inFiles=wf['primVars'][inpID][outFile[0]]
%matplotlib qt
import matplotlib.pyplot as plt
"""

# Given a set of input files, create objects that can be worked with
import xarray as xr
import pickle
import sys
from cdo import Cdo
import numpy as np
from . import helpers 

#-----------------------------------------------------------------
def defaultImport(config, inFiles, inpID):
	"""
	Default import function
	
	Builds a set of input files into a single xarray-based dataset object

	Args:
		config (_type_): Configuration object
		inFiles (_type_): List of input files
		inpID (_type_): ID of the input files
	"""
	# Get input configuration
	thisInp = config["inputs"][inpID]

	# Make dataset object using xarray lazy load approach.
	# Apply a manual sort ensures that the time axis is correct
	# Use the join="override" argument to handle the case where
	# there are small numerical differences in the values of the
	# coordinates - in this case, we take the coordinates from the first file
	dsIn =xr.open_mfdataset(inFiles,
							combine='nested',
							use_cftime=True, 
							join="override", 
							concat_dim='time')
	dsIn=dsIn.sortby('time')

	# Select the desired variable and rename it
	ds = dsIn.rename({thisInp["internalVarName"]: thisInp["varID"]})
	da = ds[thisInp["varID"]]  # Convert to dataarray

	# Drop degenerate dimensions. If any remain, throw an error
	da = da.squeeze(drop=True)
	if len(da.dims) != 3:
		sys.exit(
			f"Extra dimensions found in processing '{inpID}' - there should be only "
			+ f"three dimensions after degenerate dimensions are dropped but "
			+ f"found {len(da.dims)} i.e. {da.dims}."
		)

	# Drop coordinates that are not associated with a dimension. Often you seen
	# height or level coming in as a coordinate, when it is perhaps more appropriate as
	# an attribute. However, different models handle this differently, and some have
	# already dropped it. The different between the two can cause problems when we
	# come to the point of merging ensemble members.
	for thisCoord in da.coords.keys():
		if len(da[thisCoord].dims)==0:
			da.attrs[thisCoord]=da[thisCoord].values
			da= da.drop_vars(thisCoord)

	return(da)


#-----------------------------------------------------------------
def cutout_lonlat(thisDat, xmin,xmax,ymin,ymax,varID):
	"""
	Apply cutout based on lonlat

	The processing chain here is to first take
	a single timeframe, and then use cdo sellonlat to perform at cutout on it. This
	is then used as a mask across the full the xarray object - this way we can
	maintain the lazy-loading and storage benefits associated with pickling, without 
	having to get our hands too dirty about dealing with unusual coordinate systems.

	Parameters
	----------
	xmin : _type_
		Minimum coordinate in the x direction
	xmax : _type_
		Maximum coordinate in the x dirction
	ymin : _type_
		Minimum coordinate in the y direction
	ymax : _type_
		Maximum coordinate in the y direction
	varID : _type_
		Name of the variable ID contained in the dataset
	"""
	# Extract first time step. This avoids having to work
	# with the entire dataset.
	# ASSERT: there is a time dimension called "time"
	firstTS=thisDat.isel(time=0)

	# Do cutouts using cdo sellonlatbox. Make sure that we
	# return a dataarray and not a dataset
	cdo = Cdo()
	cutoutMask = cdo.sellonlatbox(xmin, xmax, ymin, ymax,
								  input=firstTS,
								  returnXArray=varID)
	
	# Apply masking to data array object
	da=thisDat.where(cutoutMask.notnull(),drop=True)

	# Done
	return(da)


#-----------------------------------------------------------------	
def buildPrimVar(config, inFiles, outFile, inpID):
	"""
	Build primary variables

	Controls the import of data and generation of primary variables

	Args:
		config (_type_): Configuration object
		inFiles (_type_): List of input files
		outFile (_type_): Output file
		inpID (_type_): Input item ID
	"""
	# Get input configuration
	thisInp = config["inputs"][inpID]

	# If an import function is defined, use that. Otherwise use the default
	if thisInp["importScriptPath"]=='':
		#Use default import
		da= defaultImport(config, inFiles, inpID)
		#Apply cutout functionality
		if config["cutouts"]["method"] == "lonlatbox":
			da=cutout_lonlat(da,
					config["cutouts"]["xmin"],
					config["cutouts"]["xmax"],
					config["cutouts"]["ymin"],
					config["cutouts"]["ymax"],
					thisInp["varID"])

	else:
		#Use a custom import
		imptFn=helpers.getExternalFunction(thisInp["importScriptPath"], thisInp["importScriptFunction"])
		da = imptFn(config, inFiles, inpID)  

	# Write the dataset object to disk, depending on the configuration
	if config['processing']['picklePrimaryVariables']:
		with open(outFile[0],'wb') as f:
			pickle.dump(da,f,protocol=-1)
	else:
		#Load into memory - this should make things go faster when writing out
		#in a chunked format. But there may be a challenge in having enough RAM
		#to work with. We work this way to start with, but may need to add a 
		#switch at some point in the future
		#We also apply a little trick here, by forcing everything to be stored as
		#netcdf "float" types as well.
		daFloat=da.astype(np.float32)
		daInMem=daFloat.compute()
		# We want the output to be actively chunked along the time dimension
		# to enable better control later in the project. We use dask to 
		# identify the chunksizes that we want 
		rechunkThisWay={}
		for d in da.chunksizes:
			if d=='time':
				rechunkThisWay[d]=400
			else:
				rechunkThisWay[d]=10
		da_tmp=da.chunk(rechunkThisWay)
		likeThis=[max(chunks) for dim, chunks in zip(da_tmp.dims, da_tmp.chunks)]
		#Now use the chunking scheme as the basis for writing out the encoding
		daInMem.to_netcdf(outFile[0],
					encoding={thisInp["varID"]:{'chunksizes':[256,16,16],
							   'zlib': True,
							   'complevel':1}})

