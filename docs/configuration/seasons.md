# KAPy seasons configuration

*Seasonal calculations in KAPy are configured through a tab-separated table, with one row per season. The available options are described here. All options are required*

## Properties

- **`id`** *(string, required)*: Unique identifier for the season. It is recommended to use a short descriptive string e.g `JJA`. Note that the id `all` cannot be used, as this is reserved for use in selecting all seasons in the indicator table. Must not contain spaces.
- **`name`** *(string, required)*: A longer description of the season. This is typically used in output files.
- **`months`** *(array)*: The month(s) to include in the seasonal definition, defined by their numbers. Multiple months are specified as a common-separated list. Duplicates are not allowed.
  - **Items** *(integer)*: Minimum: `1`. Maximum: `12`.
