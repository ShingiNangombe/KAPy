## New Features
* Add ability to select multiple seasons with an indicator #36
* Secondary variables working again, after being disable in v0.5 #119
* Add use of dask to handle larger-than-memory calibration tasks #133
* Add deltas/changes in indicators #137
* Regridding handles land-sea masking via NaNs #140
* Grids can be specified as template .nc files, where the NaNs in the template will also mask the regridded output from KAPy #141

## Breaking Changes
* Removed time-binning for months #81
* Addition of deltaType argument in indicator configuration table requires adjustments to this file.

## Major Changes

## Minor changes and bug fixes
* Fixed plotting bug when working with eastings and northings #112
* 
