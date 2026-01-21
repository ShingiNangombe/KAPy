#!/usr/bin/env python
# coding: utf-8

import xesmf as xe
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
import numpy as np
import xsdba as sdba
import warnings
import os
import glob
import cftime
warnings.filterwarnings("ignore")
xr.set_options(display_style="text")


# Directories
DATADIR = '~/correcting_Tmin_tmax_together/1.first_KAPy_computation/outputs/1.variables/'
DATADIR1 = '~/ERA5_data/monthly_Africa/'
OUTDIR = '~/correcting_Tmin_tmax_together/2.bc_Python_computation/processed/'

os.makedirs(OUTDIR, exist_ok=True)
# ----------------------------
# Observation files 
obs_files = {"tmax": f"{DATADIR1}era5_tmax-Ghana.nc","tmin": f"{DATADIR1}era5_tmin-Ghana.nc","t2m":  f"{DATADIR1}era5_t2m-Ghana.nc",}

obs_files = {
"tmax": f"{DATADIR1}era5_tmax_monthly_Ghana.nc",
"tmin": f"{DATADIR1}era5_tmin_monthly_Ghana.nc",
"t2m": f"{DATADIR1}era5_t2m_monthly_Ghana.nc",
}

def load_and_convert(path, var):
    """
Load OBS variable, convert from Kelvin to Celsius,
and convert calendar to noleap without touching time structure.
    """
    da = xr.open_dataset(path)[var]
    da = da.convert_calendar("noleap", use_cftime=True, align_on="date")
    da.sel(time=slice("1991", "2020")).resample(time="M").mean()
    return da
obs = {k: load_and_convert(v, k) for k, v in obs_files.items()}
# Reversed latitude for observation
obs_sliced1 = {k: v.sel(time=slice("1991", "2020")).reindex(lat=list(reversed(v.lat))) for k, v in obs.items()}

# Helper functions
def slice_periods(da):
    """Slice dataset into historical reference and full period."""
    return {
        "hist_ref": da.sel(time=slice("1991", "2020")).resample(time="M").mean(),
        "all":      da.sel(time=slice("1949", "2100")).resample(time="M").mean(),}

def make_regridder(input_da, target_grid):
    """Create a regridder for one variable based on its own grid."""
    return xe.Regridder(
        input_da,
        target_grid,
        method="bilinear",
        extrap_method="nearest_s2d",
        reuse_weights=False)

def load_var(filepath, varname):
    """Load variable and preserve original time coordinates."""
    da = xr.open_dataset(filepath)[varname]
    da = da.convert_calendar("noleap", use_cftime=True, align_on="date")
    return da

def force_monthly_first_day(da):
    """
    Rebuild monthly timestamps so they line up across variables.
    Uses the start year from the input DataArray.
    """
    n = da.sizes["time"]
    # Get the start year from the model's first time step
    start_year = da.time.dt.year[0].item()
    new_time = xr.cftime_range(
        start=f"{start_year}-01-01",
        periods=n,
        freq="MS",
        calendar="noleap")
    da = da.copy()
    da["time"] = new_time
    return da
# ----------------------------
# Load OBS grid for regridding
lat, lon = obs_sliced1["tmax"].lat, obs_sliced1["tmax"].lon
obs_grid = xr.Dataset({
    "lat": xr.DataArray(lat, dims="lat", attrs={"units": "degrees_north"}),
    "lon": xr.DataArray(lon, dims="lon", attrs={"units": "degrees_east"}),})
# ----------------------------
# Discover files
tasmax_files = sorted(glob.glob(f"{DATADIR}tasmax/tasmax_CORDEX*.nc"))
tasmin_files = sorted(glob.glob(f"{DATADIR}tasmin/tasmin_CORDEX*.nc"))
tas_files    = sorted(glob.glob(f"{DATADIR}tas/tas_CORDEX*.nc"))
all_files = list(zip(tasmax_files, tasmin_files, tas_files))
var_names = ["tasmax", "tasmin", "tas"]

# ----------------------------
# MAIN LOOP — per model
def get_model_id(path):
    """Extract model ID from filepath."""
    base = os.path.basename(path)
    parts = base.split("_")
    return "_".join(parts[1:]).split(".nc")[0]

def get_original_filename(path):
    """Extract just the filename without directory path."""
    return os.path.basename(path)

def compute_mean_dtr_z(tmax, tmin, tas):
    """Compute mean temperature, diurnal temperature range, and z parameter."""
    tmean = tas
    dtr = tmax - tmin
    z = tas - (tmax + tmin) / 2
    return tmean, dtr, z

def qdm_correction(ref, hist, target):
    """Apply Quantile Delta Mapping bias correction."""
    QDM = sdba.QuantileDeltaMapping.train(ref=ref, hist=hist, nquantiles=20, group="time.month")
    out = QDM.adjust(target, extrapolation="constant", interp="nearest")
    return xr.where(out < 0, 0, out)

def standardize_monthly_time(da):
    """Force monthly data to use the first day of each month."""
    new_time = xr.cftime_range(
        start=str(da.time.dt.year[0].item()) + "-01-01",
        periods=len(da.time),
        freq="MS",
        calendar="noleap")
    da = da.copy()
    da["time"] = new_time
    return da

obs_sliced = {var: standardize_monthly_time(da) for var, da in obs_sliced1.items()}
for tasmax_f, tasmin_f, tas_f in all_files:
    # Determine model ID from tasmax
    model_id = get_model_id(tasmax_f)
    print(f"\n=== Processing {model_id} ===")    
    file_set = [tasmax_f, tasmin_f, tas_f]
    processed = {}    
    # Store original filenames for each variable
    original_filenames = {
        "tasmax": get_original_filename(tasmax_f),
        "tasmin": get_original_filename(tasmin_f), 
        "tas": get_original_filename(tas_f)}

    # Process 3 variables
    for filepath, var in zip(file_set, var_names):
        print(f" → variable: {var}")
        da = load_var(filepath, var)
        sliced = slice_periods(da)
        regridder = make_regridder(sliced["hist_ref"], obs_grid)
        processed[var] = {period: regridder(data) for period, data in sliced.items()}
    for var in processed:
        for period in processed[var]:
            processed[var][period] = force_monthly_first_day(processed[var][period])       
    obs_tmean, obs_dtr, obs_z = compute_mean_dtr_z(
        obs_sliced['tmax'],
        obs_sliced['tmin'],
        obs_sliced['t2m'],)
    # Dictionaries to store model diagnostics
    mod_tmean, mod_dtr, mod_z = (
        {"hist_ref": None, "all": None},
        {"hist_ref": None, "all": None},
        {"hist_ref": None, "all": None})    
    for p in ["hist_ref", "all"]:
        tmean, dtr, z = compute_mean_dtr_z(    #compute mean dtr and z
            processed["tasmax"][p],
            processed["tasmin"][p],
            processed["tas"][p],)       
        mod_tmean[p] = tmean.rename("tmean")
        mod_dtr[p] = dtr.rename("dtr")
        mod_z[p] = z.rename("z")

    # Set units attributes
    mod_dtr["hist_ref"].attrs['units'], mod_dtr["all"].attrs['units'], obs_dtr.attrs['units'] = '°C', '°C', '°C'
    mod_z["hist_ref"].attrs['units'], mod_z["all"].attrs['units'], obs_z.attrs['units'] = '°C', '°C', '°C'
    mod_tmean["hist_ref"].attrs['units'], mod_tmean["all"].attrs['units'], obs_tmean.attrs['units'] = '°C', '°C', '°C'

    # Apply bias correction
    dtr_bc_all = qdm_correction(obs_dtr, mod_dtr["hist_ref"], mod_dtr["all"])
    z_bc_all = qdm_correction(obs_z, mod_z["hist_ref"], mod_z["all"])
    tmean_bc_all = qdm_correction(obs_tmean, mod_tmean["hist_ref"], mod_tmean["all"])

    dtr_bc_all = xr.where(dtr_bc_all < 0, 0, dtr_bc_all)  # conditing that the lowest dtr is zero,since tmin can not be > 0
    tmax_bc_all = tmean_bc_all - z_bc_all + dtr_bc_all / 2
    tmin_bc_all = tmean_bc_all - z_bc_all - (dtr_bc_all / 2)
    # Sanity check
    assert (tmax_bc_all >= tmin_bc_all).all(), "Some Tmax < Tmin after bias correction!"

    bc_hist = {"tasmin": tmin_bc_all.rename("tasmin"),
        "tasmax": tmax_bc_all.rename("tasmax"),
        "tas": tmean_bc_all.rename("tmean"),}

    # ----------------------------
    # SAVE OUTPUT with original input filenames
    for var, da in bc_hist.items():
        # Get original filename for this variable
        orig_name = original_filenames[var]        
        # Remove .nc extension if present
        if orig_name.endswith('.nc'):
            base_name = orig_name[:-3]  # Remove .nc
        else:
            base_name = orig_name     
        # Create output filename with _B_all suffix (since bc_hist contains the "all" period)
        outname = f"{OUTDIR}{base_name}.nc"
            # ---- SKIP IF FILE EXISTS ----
        if os.path.exists(outname):
            print(f"Skipping {outname}: file already exists.")
            continue
    # ------------------------------
# Ensure the correct dimension order
        da = da.transpose("time", "lat", "lon")
        da = da.convert_calendar("gregorian")
# ---- Set coordinate attributes ----
        da = da.assign_coords(
            lat = da.lat.assign_attrs({
              "units": "degrees_north"
               }),
            lon = da.lon.assign_attrs({
               "units": "degrees_east"
               })
         )
        da.encoding["_FillValue"] = np.nan
# For safety: apply also to underlying DataArray variable encoding
        for v in da.data_vars if hasattr(da, "data_vars") else [da]:
            da.encoding["_FillValue"] = np.nan
        print(f"Saving bias-corrected {var} of {base_name}.nc")
        da.to_netcdf(
            outname,
            encoding={da.name: {"_FillValue": np.nan}},  # explicit per-variable encoding
        )

