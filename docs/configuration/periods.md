# KAPy periods configuration

*Calculation periods in KAPy are configured through a tab-separated table, with one row per period. At least one period must be defined, even in configurations where there is no `period` time-binning used, as the first period is used as the reference period against which changes in indicators are calculated. The available options are described here. All options are required.*

## Properties

- **`id`** *(string, required)*: Unique identifier for the period. This can be numeric, but will be treated as a string.
- **`name`** *(string, required)*: A longer description of the period. This is typically used in the x-axes of plots, so shouldn't be TOO long!
- **`start`** *(string, required)*: The start year of the period. The full year is included in the calculation.
- **`end`** *(string, required)*: The end year of the period. The full year is included in the calculation.
