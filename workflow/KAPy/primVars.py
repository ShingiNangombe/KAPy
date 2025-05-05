"""
#Setup for debugging with VSCode
import os
print(os.getcwd())
os.chdir("KAPy/workflow")
import KAPy
os.chdir("../..")
print(os.getcwd())
config=KAPy.getConfig("./config/config.yaml")  
wf=KAPy.getWorkflow(config)
inpID=list(wf['primVars'].keys())[0]
outFile=list(wf['primVars'][inpID])[0]
inFiles=wf['primVars'][inpID][outFile]
import KAPy.helpers as helpers
import KAPy.workflow as workflow
%matplotlib inline
"""

# Given a set of input files, create objects that can be worked with
import xarray as xr
import pickle
import sys
import time
from cdo import Cdo
import numpy as np
import xclim 
import pandas as pd
import glob
import os
from . import helpers 
from . import workflow

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
	time_coder=xr.coders.CFDatetimeCoder(use_cftime=True)
	try:
		dsIn =xr.open_mfdataset(inFiles,
								combine='nested',
								decode_times=time_coder, 
								join="override", 
								chunks={'time':256},
								concat_dim='time')
	except Exception as e:
		raise RuntimeError(f"Opening following NetCDF files failed: '{inFiles}'\n{e}")

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

	# Unit handling -----------------------------
	# Note that this is enforced here, even if it is already handled in the custom
	# configuration. There are three separate cases we need to handle

	# Case 1 - no units attribute on da: 
	# => Set units directly but fail if not specified
	if not 'units' in da.attrs:
		if thisInp['units']=='':
			raise ValueError(f"Units argument for inputID '{inpID}' is blank but needs to be supplied in cases where there are no units in the input file.")
		else:
			da.attrs['units'] = thisInp['units']

	# Case 2 - da has units, but argument is null:
	# => leave as in

	# Case 3 - da has units, argument is specified
	# => Convert units of data to specified
	elif not thisInp['units']=='':
		da=xclim.core.units.convert_units_to(da,thisInp['units'])
	
	# Check that the unit choice is sane

	# Output --------------------
	# Write the dataset object to disk, depending on the configuration
	if config['processing']['picklePrimaryVariables']:
		with open(outFile[0],'wb') as f:
			pickle.dump(da,f,protocol=-1)
	else:
		#We also apply a little trick here, by forcing everything to be stored as
		#netcdf "float" types as well.
		daFloat=da.astype(np.float32)
		#Set chunking
		defaultChunks=[256,16,16]
		chunkThisWay=[min(defaultChunks[i],daFloat.shape[i]) for i in range(0,3)]
		
		#Now use the chunking scheme as the basis for writing out the encoding
		try:
			daFloat.to_netcdf(outFile[0],
						encoding={thisInp["varID"]:{'chunksizes':chunkThisWay,
								'zlib': True,
								'complevel':1}})
		except Exception as e:
			raise RuntimeError(f"Writing NetCDF file '{outFile[0]}' to disk failed with error: {e}") 

def VariableOverview(config):
	#Get workflow
	wf=workflow.getWorkflow(config)

	# Get the list of primaryVar files from the workflow and
	# complement with directory search of existing files.
	# TODO:
	#  - Remove duplicates
	#  - Split fname into fields
	#  - Calculate differences
	wfFiles=[ g for k in wf['primVars'].keys() for g in wf['primVars'][k]]
	ncFiles=glob.glob(config['dirs']['variables']+"/**/*.nc",recursive=True)
	pklFiles=glob.glob(config['dirs']['variables']+"/**/*.pkl",recursive=True)
	tbl= pd.DataFrame(sorted(set(wfFiles+ncFiles+pklFiles)),columns=["path"])
	tbl['filename']=[os.path.basename(f) for f in tbl["path"]]
	tbl["varID"] = tbl["filename"].str.extract("^([^_]+)_.*$")
	tbl["datasetID"] = tbl["filename"].str.extract("^[^_]+_([^_]+)_.*$")
	tbl["gridID"] = tbl["filename"].str.extract("^[^_]+_[^_]+_([^_]+)_.*$")
	tbl["expt"] = tbl["filename"].str.extract("^[^_]+_[^_]+_[^_]+_([^_.]+).*$")
	tbl["ensemble_member"] = tbl["filename"].str.extract("^[^_]+_[^_]+_[^_]+_[^_]+_(.+).nc(?:.pkl)?$")
	tbl['in_workflow']=[f in wfFiles for f in tbl["path"]]

	#ChatGPT made this nice little progress bar for us
	def snakemake_progress(i, total, start_time, prefix='', length=40):
		elapsed = time.time() - start_time
		percent = (i / total) * 100
		filled_length = int(length * i // total)
		bar = '█' * filled_length + '-' * (length - filled_length)

		# Estimate remaining time
		eta = (elapsed / i) * (total - i) if i > 0 else 0
		eta_str = time.strftime('%H:%M:%S', time.gmtime(eta))

		print(f'\r{prefix} |{bar}| {percent:6.2f}% ETA: {eta_str}', end='', flush=True)
		if i == total:
			print()	

	#Now loop over the files
	outList=[]
	startTime=time.time()
	print(f"Processing {tbl.shape[0]} files...")
	for thisidx,thisrw in tbl.iterrows():
		#Basic progress bar
		snakemake_progress(thisidx,tbl.shape[0],startTime)

		#Check that object exists
		thisrw['file_exists']=os.path.exists(thisrw['path'])
		#If the file exists, load it
		if thisrw['file_exists']:
			#Try to load the file
			try:
				dat=helpers.readFile(thisrw['path'])
				thisrw['loadsOK']=True
			except Exception as e:
				thisrw['loadsOK']=False

			#Extract useful info if possible
			if thisrw['loadsOK']:
				thisrw['calendar']=dat.time.values[0].calendar
				thisrw['start_date']=min(dat.time.values).strftime("%Y-%m-%d")
				thisrw['end_date']=max(dat.time.values).strftime("%Y-%m-%d")
				thisrw['time_span']=(max(dat.time.values)-min(dat.time.values)).days
				thisrw['time_points']=dat.time.size
				thisrw['gaps']=thisrw['time_points']-thisrw['time_span']-1

		#Store outputs
		outList+=[thisrw]

	#Output results
	out=pd.DataFrame(outList)
	cols = out.columns.tolist()
	reordered_cols = cols[2:] + cols[:2]
	out = out[reordered_cols]
	out=out.sort_values(by=['varID','datasetID','gridID',"expt","ensemble_member"])
	outFname=os.path.join(config['dirs']['variables'],"Variable_overview.csv")
	print(f"\nWriting output to '{outFname}'.\n")
	out.to_csv(outFname,index=False)

