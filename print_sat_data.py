#!/usr/bin/env python
# coding: utf-8
import logging
import datetime
import numpy as np

# Define the logger
LOG = logging.getLogger(__name__)
DATE_FORMAT = "%Y%m%d%H%M%S"

class SatDataException(Exception):
    pass


def get_files_from_datadir(data_dir, date_from, date_to):
    """
    Getting the files from the data dir.
    It does a walk through the data dir and finds files that
    - Starts with a date in the specified date range.
    - Contains the string "-DMI-L4"
    - Ends with .nc
    """
    LOG.debug("Data dir: '%s'"%data_dir)
    LOG.debug("Date from: '%s'."%date_from)
    LOG.debug("Date to: '%s'."%date_to)

    # Make sure that date_from allways is before date_to.
    date_from = min(date_from, date_to)
    date_to   = max(date_from, date_to)

    for root, dirs, files in os.walk(data_dir):
        # Walk through every files/directories in the data dir.
        # 20150313000000-DMI-L4_GHRSST-SSTfnd-DMI_OI-NSEABALTIC-v02.0-fv01.0.nc.gz
        # f.endswith((".nc", ".nc.gz"))
        for filename in [f for f in files
                         if f.endswith(".nc")
                         and "-DMI-L4" in f
                         and date_from <= datetime.datetime.strptime(f.split("-")[0], DATE_FORMAT).date() <= date_to]:
            yield os.path.abspath(os.path.join(root, filename))

def get_lat_lon_ranges(input_filename):
    """
    Getting the lat long ranges from a input file.

    Opens the file, reads the lat/lon arrays and finds the min/max values.
    """
    nc = netCDF4.Dataset(input_filename)
    try:
        return [min(nc.variables['lat']), max(nc.variables['lat'])], [min(nc.variables['lon']), max(nc.variables['lon'])]
    finally:
        nc.close()

def get_variable_names(input_filename):
    """
    Gets the variable names in the file. That means the variables that can be read from the file.
    """
    LOG.debug("Getting variable names from %s"%input_filename)
    nc = netCDF4.Dataset(input_filename)
    try:
        return {str(var) for var in nc.variables}
    finally:
        nc.close()

def variables_is_in_file(required_variables, input_filename):
    """
    Makes sure that the variables in the "required_variables"
    can actually be found in the file.
    """
    assert(isinstance(required_variables, list))

    variable_names = get_variable_names(input_filename)
    for required_variable in required_variables:
        if required_variable not in variable_names:
            LOG.warning("The file, '%s', must have the variable '%s'."%(input_filename, required_variable))
            return False
    return True

def get_available_dates(data_dir):
    """
    Gets the dates that are availabe.

    That is, it
    - finds all the relevant files (see get_files_from_datadir) in the data dir,
    - parses the filenames
    - returns the date from the filename (not the content of the file).
    """
    date_from = datetime.datetime(1981, 1, 1).date()
    date_to = datetime.datetime.now().date() + datetime.timedelta(days = 1)
    for filename in get_files_from_datadir(data_dir, date_from, date_to):
        yield datetime.datetime.strptime(os.path.basename(filename).split("-")[0], "%Y%m%d%H%M%S").date()

def get_closest_lat_lon_indexes(input_filename, lat, lon):
    """
    Gets the indexes for the specified lat/lon values.

    E.g. analysed_sst is a grid. The indexes correspond to (time, lat, lon).
    Time is only one dimension in our files, so we need the lat / lon indexes.

    TODO:
                     LON
    +-----+-----+-----+-----+-----+-----+
    |  x  |  x  |  x  |  x  |  x  |  x  |
    +-----+-----+-----+-----+-----+-----+ LAT
    |  x  |  x  |  x  |  x  |  x  |  x  |
    +-----+-----+-----+-----+-----+-----+
    
    The lat/lon points are the center values in the grid cell.
    The edges are therefore not included below. Fix this by:
    - adding grid_width/2 to the max lon values
    - subtract grid_width/2 to the min lon valus
    - adding grid_height/2 to the max lat values
    - subtract grid_height/2 to the min lat valus
    """
    LOG.debug("Filename: %s"%(input_filename))
    lats, lons = get_lat_lon_ranges(input_filename)
    
    # TODO: Missing the edges!!
    # lat[0] - grid_cell_height/2, lat[1] + grid_cell_height/2
    if not lats[0] <= lat <= lats[1]:
        raise SatDataException("Latitude %s is outside latitude range %s."%(lat, " - ".join([str(l) for l in lats])))
    
    # lon[0] - grid_cell_width/2, lon[1] + grid_cell_width/2
    if not lons[0] <= lon <= lons[1]:
        raise SatDataException("Longitude %s is outside longitude range %s."%(lon, " - ".join([str(l) for l in lons])))

    nc = netCDF4.Dataset(input_filename)
    try:
        return abs((nc.variables['lat'] - np.float32(lat))).argmin(), abs((nc.variables['lon'] - np.float32(lon))).argmin()
    finally:
        nc.close()

def get_values(input_filename, lat, lon, variables_to_print, ignore_missing=False):
    """
    Getting the values for the specified lat / lon values.

    It gets the indexes closest to lat/lon and
    returns a list of the values specified in variables_to_print.

    If one of the values are missing, None will be returned,
    unless ignore_missing is True. That will return the
    list even with missing values.
    """    
    # Get the closes indexes for the lat lon.
    LOG.debug("Getting the values from the file.")

    LOG.debug("Getting the indexes for lat/lon: %f/%f"%(args.lat, args.lon))
    lat_index, lon_index = get_closest_lat_lon_indexes(input_filename, lat, lon)

    LOG.debug("The lat/lo indexes for %f/%f were: %i, %i"%(lat, lon, lat_index, lon_index))

    # Do the work.
    nc = netCDF4.Dataset(input_filename)
    try:
        items_to_print = []
        one_of_the_values_are_missing = False
        for variable_name in variables_to_print:
            LOG.debug("Adding variable name: %s."%(variable_name))
            if variable_name == "lat":
                items_to_print.append(nc.variables['lat'][lat_index])
            elif variable_name == "lon":
                items_to_print.append(nc.variables['lon'][lat_index])
            elif variable_name == "time":
                # The time variable is seconds since 1981-01-01.
                start_date = datetime.datetime(1981, 1, 1)
                items_to_print.append((start_date + datetime.timedelta(seconds=int(nc.variables['time'][0]))))
            else:
                variable = nc.variables[variable_name][0][lat_index][lon_index]
                if variable.mask:
                    one_of_the_values_are_missing = True
                items_to_print.append(variable)

        LOG.debug("Checking if any of the values are missing.")
        if one_of_the_values_are_missing:
            LOG.debug("Checking if we are to print the values or not even if one of the values are missing.")
            if ignore_missing:
                LOG.debug("Returning None because one fo the values were missing.")
                return None

        # There were no missing values or we will return it after all...
        LOG.debug("Converting all items to string")
        items_to_print = map(lambda x: str(x), items_to_print)

        # Returning the items list.
        LOG.debug("Items to string: %s"%(items_to_print))
        return items_to_print
    finally:
        nc.close()


if __name__ == "__main__":
    import sys
    import os
    import netCDF4
    import glob

    try:
        import argparse
    except Exception, e:
        print ""
        print "Try running 'sudo apt-get install python-argparse' or 'sudo easy_install argparse'!!"
        print ""
        raise e

    def date( date_string ):
        return datetime.datetime.strptime(date_string, '%Y-%m-%d').date()

    def directory(path):
        if not os.path.isdir(path):
            raise argparse.ArgumentTypeError("'%s' does not exist. Please specify save directory!"%(path))
        return path

    def file(path):
        if not os.path.isfile(path):
            raise argparse.ArgumentTypeError("'%s' does not exist. Please specify input file!"%(path))
        return path

    parser = argparse.ArgumentParser(description='Print the data point for a specified lat / lon.')
    parser.add_argument('--data-dir', type=directory, help='Specify the directory where the data files can be found. Ignored if --input-filename is set. It still must exist, though. The files in the data dir must be of the form "<YYYYMMDD>000000-DMI-L4*.nc", e.g: "20150310000000-DMI-L4_GHRSST-SSTfnd-DMI_OI-NSEABALTIC-v02.0-fv01.0.nc".', default=os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sat"))


    parser.add_argument('--print-variables', action="store_true", help="Print the available variables.")
    parser.add_argument('--print-lat-lon-range', action="store_true", help="Print the max/min lat/lon values in the file.")
    parser.add_argument('--print-dates', action="store_true", help="Print the dates available in the data-dir. The dates are based on the file names in the data directory.")

    parser.add_argument('-f', '--filter', action="append", nargs="*", help="Only return a string with some of the values. Based on the header file. --print-variables to see the available filter options.")

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-d', '--debug', action='store_true', help="Output debugging information.")
    group.add_argument('-v', '--verbose', action='store_true', help="Output info.")

    parser.add_argument('--log-filename', type=str, help="File used to output logging information.")

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--input-filename', type=file, help="Input filename.")
    group.add_argument('--date', type=date, help='Only print data values from (including) this date.', default=datetime.datetime.now().date())
    group.add_argument('--date-from', type=date, help='Only print data values from (including) this date.')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--date-to', type=date, help='Only print data untill (exclusive) this date.')
    group.add_argument('--days-back-in-time', type=int, help='Only print data from --date or --date-from and this number of days back in time.')
    group.add_argument('--days-forward-in-time', type=int, help='Only print data from --date or --date-from and this number of days forward in time.')

    parser.add_argument("--ignore-missing", action="store_true", help="Add this option to print the values even though one of them are missing.")
    parser.add_argument("--lat", type=float, help="Specify which latitude value to use.")
    parser.add_argument("--lon", type=float, help="Specify which longitude value to use get.")
     
    # Do the parsing.
    args = parser.parse_args()

    # Set the log options.
    if args.debug:
        logging.basicConfig(filename=args.log_filename, level=logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(filename=args.log_filename, level=logging.INFO)
    else:
        logging.basicConfig(filename=args.log_filename, level=logging.WARNING)

    # Output what is in the args variable.
    LOG.debug(args)

    if args.input_filename:
        input_files = [args.input_filename,]
    else:
        # Date is allways set to the date to start from.
        if args.date_from:
            args.date = args.date_from

        # Date to. 
        if args.days_back_in_time:
            args.date_to = args.date - datetime.timedelta(days = args.days_back_in_time)
        elif args.days_forward_in_time:
            args.date_to = args.date + datetime.timedelta(days = args.days_back_in_time)
        # if date_to has not been set by the two above:
        if not args.date_to:
            # Date is set one day forward.
            args.date_to = args.date + datetime.timedelta(days = 1)

        input_files = list(get_files_from_datadir(args.data_dir, args.date, args.date_to))

    if len(input_files) == 0:
        print "No files to get data from... Please specify date (--date) or date range (--date-from/--date-to)."
        print "Use --help for details."
        print ""
        print "Data dir: '%s'."%(os.path.abspath(args.data_dir))

    LOG.debug("Date from: %s. Date to: %s."%(args.date, args.date_to))

    try:
        # Print the dates availabe by filenames (in the datadir).
        if args.print_dates or len(input_files) == 0:
            assert(os.path.isdir(args.data_dir))
            date_strings = [date.strftime("%Y-%m-%d") for date in get_available_dates(args.data_dir)]
            date_strings.sort()
            print "Available dates:"
            print ", ".join(date_strings)
            if len(input_files) == 0:
                sys.exit(1)
            sys.exit()

        # print lat/lon ranges.
        if args.print_lat_lon_range:
            for input_filename in input_files:
                lats, lons = get_lat_lon_ranges(input_filename)
                print ""
                print "Filename: '%s'"%(input_filename)
                print "Lats: %s"%(" - ".join([str(lat) for lat in lats]))
                print "Lons: %s"%(" - ".join([str(lon) for lon in lons]))
            sys.exit()

        # Print variable names.
        if args.print_variables:
            for input_filename in input_files:
                variable_names = get_variable_names(input_filename)
                print "Available variables for %s:"%(input_filename)
                print "'%s'"%("', '".join(variable_names))
                sys.exit()

        # Print the values.
        for input_filename in input_files:
            assert(variables_is_in_file(["lat", "lon"], input_filename))

            # Filtering.
            # It was not really possible to create a default filter with argparse. The new filter variables were inserted
            # into a new list, alongside the default list.
            variables_to_print = []
            if args.filter == None:
                args.filter = [None,]
                variables_to_print = get_variable_names(input_filename)
            else:
                # Just make sure the filter variable is a list, and not a str, e.g.
                assert(isinstance(args.filter, list))
                variables_to_print = args.filter[0]

            assert(variables_is_in_file(variables_to_print, input_filename))
            print "# %s"%(" ".join(variables_to_print))

            values = get_values(input_filename, args.lat, args.lon, variables_to_print, ignore_missing=args.ignore_missing)
            print values
            sys.exit()
                


    except argparse.ArgumentTypeError, e:
        print("")
        print("Error: %s"%(e.message))
        sys.exit(1)