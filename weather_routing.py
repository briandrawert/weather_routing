

import datetime
import pandas
import pytz
import time
import requests
import os.path
import math
import pygrib
import pickle
import copy

shore_boundaries=[
  [ (33.72042, -118.20665), #Long breach, PV
    (33.7025267, -118.25570833),
    (33.70421,-118.29362),
    (33.71349, -118.31815667),
    (33.73722, -118.40627),
    (33.77504, -118.42992) ],
  [ (33.30681, -118.14915),# Catalina 
    (33.31505, -118.28944), 
    (33.40954, -118.36371),
    (33.47957, -118.53720),
    (33.47954, -118.60711),
    (33.44873, -118.59738),
    ]
]







def route_isochrons(waypoints, start_date, start_time, wind_data_dir=None, time_step_size = 1):
    """ Weather routing with isochrons """
    (FCdate, FCtime,_) = get_grib_time(start_date, start_time)               

    isochrons=[[
        [{  #start
            'lat': waypoints.iloc[0]['lat'],
            'lng': waypoints.iloc[0]['lng'],
            'date': FCdatetime_to_localtime(FCdate, FCtime,0),
            'dtw' : haversine_distance(
                        waypoints.iloc[0]['lat'],waypoints.iloc[0]['lng'],
                        waypoints.iloc[1]['lat'],waypoints.iloc[1]['lng']), #Distance to Waypoint
            'tdt' : 0, #total distance travled
        }]
    ]]
    
    simulation_time = 0
    max_step_debug = 10
    for wp_ndx in range(1,len(waypoints)):
        n_steps = 0
        print(f"========== routing to waypoint {wp_ndx} ===========")
        lat_start = waypoints.iloc[wp_ndx-1]['lat']
        lng_start = waypoints.iloc[wp_ndx-1]['lng']
        lat_end = waypoints.iloc[wp_ndx]['lat']
        lng_end = waypoints.iloc[wp_ndx]['lng']
    
        found_wp = False
        ###
        while not found_wp:
            n_steps +=1
            if n_steps > max_step_debug:
                print(f"n_steps={n_steps} > max_step_debug={max_step_debug}")
                return isochrons
            simulation_time += 1
            print(f"Calculating simulation_time={simulation_time}")
            convex_hull = take_isochron_step(
                    isochrons[simulation_time-1], simulation_time-1, FCdate, FCtime, 
                    wind_data_dir,lat_start,lng_start,lat_end, lng_end, time_step_size) 
            isochrons.append(convex_hull)
            ####
            min_route = None
            for route in convex_hull:
                #print(route[-1])
                if min_route is None or route[-1]['dtw'] < min_route[-1]['dtw']:
                    min_route = route
            print(f"  dtw={min_route[-1]['dtw']:.3f} sog={min_route[-1]['sog']:.3f}", end='')
            if min_route[-1]['dtw'] < min_route[-1]['sog']:
                found_wp = True
                print(" === found waypoint",end='')
                ###
                # add a partial step to the min_route
                min_route.append(
                    {
                        'lat':lat_end,
                        'lng':lng_end,
                        'mag':min_route[-1]['mag'],
                        'sog':min_route[-1]['sog'],
                        'dtw':0,
                        'twa':0,
                        'tdt':min_route[-1]['tdt']+min_route[-1]['dtw'],
                        'date':FCdatetime_to_localtime(FCdate, FCtime,simulation_time),
                    }
                )
                isochrons.append([min_route])
                ###
            print()
    ####
    return isochrons




def take_isochron_step(parent_isochron, simulation_time, FCdate, FCtime, wind_data_dir,
                       lat_start,lng_start,lat_end, lng_end, time_step_size,
                       max_deviation_angle=90, max_turn_angle=120, max_chull_segment_len=2.5):
    isochron=[]
    (grib_file_date, grib_file_time, hr_offset) = get_grib_time(FCdate, FCtime, simulation_time)
    min_dtw = None
    ###
    for past_traveled_path in parent_isochron:
        lat = past_traveled_path[-1]['lat']
        lng = past_traveled_path[-1]['lng']
        ###
        wind_data = load_historical_gfs_forecast(wind_data_dir, grib_file_date, 
                                                          grib_file_time, hr_offset)
        (tws, twd) = get_wind_at_location_from_data(wind_data, lat, lng)
        polars = polar_rhiannon(tws)
        parent_isochron_routes = get_parent_isochron_routes(parent_isochron,lat,lng)
        ###
        boat_mag_history={}
        for (angle,boat_speed) in polars:
            for delta_angle in (angle, -1*angle):
                boat_mag = (twd+delta_angle)%360
                ##
                if boat_mag in boat_mag_history: continue
                boat_mag_history[boat_mag]=1
                ##
                dev_angle = calculate_deviation(lat, lng, lat_end, lng_end, boat_mag)
                # check if we should prune the path
                if dev_angle > max_deviation_angle:
                    #print(f"   mag {boat_mag} deviation={dev_angle} too big")
                    continue                
                if simulation_time > 0: # don't calculate turn angle on step 1
                    turn_angle =  math.fabs((past_traveled_path[-1]['mag'] - boat_mag + 540) % 360 - 180)
                    if turn_angle > max_turn_angle:
                        #print(f"    mag {boat_mag} turn_angle={turn_angle} too big ")
                        continue
                ##
                (dlat,dlng) = calculate_destination_latlng(lat,lng,boat_speed,boat_mag,time_step_size) # hour
                dist_traveled = time_step_size * boat_speed
                ##
                if does_path_cross_boundary(lat, lng, dlat, dlng, shore_boundaries):
                    #print(f"    mag {boat_mag} crosses land")
                    continue
                if does_path_cross_parent_path(lat,lng, dlat, dlng, parent_isochron_routes):
                    #print(f"    mag {boat_mag} crosses parent route")
                    continue
                # save the path
                #print(f"mag {boat_mag} ({lat},{lng}) ({dlat},{dlng})")
                traveled_path = copy.copy(past_traveled_path)
                traveled_path.append({
                    'lat':dlat,
                    'lng':dlng,
                    'mag':boat_mag,
                    'sog':boat_speed,
                    'dtw':haversine_distance(dlat,dlng,lat_end,lng_end),
                    'twa':angle,
                    'tdt':past_traveled_path[-1]['tdt']+dist_traveled,
                    'date':FCdatetime_to_localtime(FCdate, FCtime,simulation_time+1),
                })
                isochron.append(traveled_path)

    #################
    # find the convex hull to represent the isochron
    #print(f"============= CONVEX HULL: start with {len(isochron)} routes")
    convex_hull = []
    # find the min_dtw point, accept it
    convex_hull.append(min(isochron, key=lambda x:x[-1]['dtw']))
    isochron = [item for item in isochron if item != convex_hull[0]]
    #print(f"min_dtw point: ({(convex_hull[0][-1]['lat'],convex_hull[0][-1]['lng'])}) mag:{convex_hull[0][-1]['mag']}")
    ################
    ################
    # first pass, sort all points into positive and negative sides, 
    positive_side = []
    negative_side = []
    for ndx,x in enumerate(isochron):
        xp = ccw_crossprod_normalized( 
                        (lat_start,lng_start),
                        (convex_hull[0][-1]['lat'],convex_hull[0][-1]['lng']),
                        (x[-1]['lat'],x[-1]['lng']) )
        if xp > 0:
            positive_side.append(x)
        else:
            negative_side.append(x)

    #TODO: first positive and negative segments are O(1) here
    ################
    # Convex Hull: Positive side
    while True:
        max_xp = None
        max_ndx = None
        max_xp_w_dist = None
        max_ndx_w_dist = None
        max_d_w_dist = None
        #print(f"hull point={ (convex_hull[-1][-1]['lat'],convex_hull[-1][-1]['lng'])} mag:{convex_hull[-1][-1]['mag']}")
        for ndx,x in enumerate(positive_side):
            xp = ccw_crossprod_normalized( 
                                (lat_start,lng_start),
                                (convex_hull[-1][-1]['lat'],convex_hull[-1][-1]['lng']),
                                (x[-1]['lat'],x[-1]['lng']) )
            if xp < 0:
                #print(f"       skipping {(x[-1]['lat'],x[-1]['lng'])} xp={xp}")
                continue
            d = haversine_distance(convex_hull[-1][-1]['lat'],convex_hull[-1][-1]['lng'],
                                    x[-1]['lat'],x[-1]['lng'])
            #print(f"       checking ({x[-1]['lat']:.3f},{x[-1]['lng']:.3f}) d={d:.3f} xp={xp:.3f} mag={x[-1]['mag']:.3f}",end='')

            if max_xp is None or xp > max_xp:
                max_xp = xp
                max_ndx = ndx
                #print(" max_xp",end='')
            if d <= max_chull_segment_len and (max_xp_w_dist is None or xp > max_xp_w_dist):
                max_xp_w_dist = xp
                max_ndx_w_dist = ndx
                max_d_w_dist = d
                #print(" max_xp_w_dist",end='')
            #print()
        if max_xp is None or max_xp <= 0:
            #print(f"  no more positive points")
            break # no positive point found, stop looking positive
        if max_ndx_w_dist is not None:
            # accept the point within the range "max_chull_segment_len"
            p = positive_side.pop(max_ndx_w_dist)
            #print(f"  accepting ({p[-1]['lat']:.3f},{p[-1]['lng']:.3f}) mag:{p[-1]['mag']:.3f}  dist={max_d_w_dist}")
            convex_hull.append( p )
        else:
            # accept any point (true convex hull algorithm)
            p = positive_side.pop(max_ndx)
            #print(f"  accepting ({p[-1]['lat']:.3f},{p[-1]['lng']:.3f}) mag:{p[-1]['mag']:.3f}  ")
            convex_hull.append( p )

    # Negative side
    while True:
        max_xp = None
        max_ndx = None
        max_xp_w_dist = None
        max_ndx_w_dist = None
        max_d_w_dist = None
        #print(f"hull point={ (convex_hull[0][-1]['lat'],convex_hull[0][-1]['lng'])} mag:{convex_hull[0][-1]['mag']}")
        for ndx,x in enumerate(negative_side):
            xp = ccw_crossprod_normalized( 
                                (lat_start,lng_start),
                                (convex_hull[0][-1]['lat'],convex_hull[0][-1]['lng']),
                                (x[-1]['lat'],x[-1]['lng']) )
            if xp >= 0:
                #print(f"       skipping {(x[-1]['lat'],x[-1]['lng'])} xp={xp}")
                continue
            ### Flip the sign of the cross product
            xp = -1 * xp
            ###
            d = haversine_distance(convex_hull[0][-1]['lat'],convex_hull[0][-1]['lng'],
                                    x[-1]['lat'],x[-1]['lng'])
            #print(f"       checking ({x[-1]['lat']:.3f},{x[-1]['lng']:.3f}) d={d:.3f} xp={xp:.3f} mag={x[-1]['mag']:.3f}",end='')
            if max_xp is None or xp > max_xp:
                max_xp = xp
                max_ndx = ndx
                #print(" max_xp",end='')
            if d <= max_chull_segment_len and (max_xp_w_dist is None or xp < max_xp_w_dist):
                max_xp_w_dist = xp
                max_ndx_w_dist = ndx
                max_d_w_dist = d
                #print(" max_xp_w_dist",end='')
            #print()
        if max_xp is None or max_xp <= 0: 
            #print(f"  no more negative points")
            break # no negative point found, stop looking negative
        if max_xp_w_dist is not None:
            # accept the point within the range "max_chull_segment_len"
            p = negative_side.pop(max_ndx_w_dist)
            #print(f"  accepting ({p[-1]['lat']:.3f},{p[-1]['lng']:.3f}) mag:{p[-1]['mag']:.3f}  dist={max_d_w_dist}")
            convex_hull.insert(0, p )
        else:
            # accept any point (true convex hull algorithm)
            p = negative_side.pop(max_ndx)
            #print(f"  accepting ({p[-1]['lat']:.3f},{p[-1]['lng']:.3f}) mag:{p[-1]['mag']:.3f}  ")
            convex_hull.insert(0, p )
    
    #print(f"============= CONVEX HULL: end with {len(convex_hull)} routes")
    return convex_hull
    



def route_all_paths(waypoints_df, hour_offset=0, start_date=None, start_time=None, 
                        wind_data_dir=None,
                        gps_bounds=None, #[min_lat,max_lat,max_lng,min_lng]
                        max_deg_deviation_from_rhumb=90):
    """
    ONLY works for 1 leg so far 
    """
    tic = time.time()
    (FCdate, FCtime,_) = get_grib_time(start_date, start_time)

    # first leg
    print(f"{waypoints_df.iloc[0]['name']} at {FCdatetime_to_localtime(FCdate, FCtime, hour_offset)}")

    # find the rhumb_route, that is the longest acceptable time
    rhumb_route, rhumb_route_t = simulate_shortest_path(
        waypoints_df.iloc[0]['lat'], waypoints_df.iloc[0]['lng'],
        waypoints_df.iloc[1]['lat'], waypoints_df.iloc[1]['lng'],
        simulation_time=hour_offset,
        FCdate=FCdate,
        FCtime=FCtime,
        wind_data_dir=wind_data_dir
        )
    print(f"Rhumb route takes {rhumb_route_t} steps")


    all_routes = simulate_all_paths(
                        waypoints_df.iloc[0]['lat'], waypoints_df.iloc[0]['lng'],
                        waypoints_df.iloc[1]['lat'], waypoints_df.iloc[1]['lng'],
                        simulation_time=hour_offset, 
                        FCdate=FCdate, FCtime=FCtime, 
                        wind_data_dir=wind_data_dir,
                        gps_bounds=gps_bounds,
                        max_deg_deviation_from_rhumb=90,
                        max_simulation_time=rhumb_route_t
                        )


    # print out calculation time
    print(f"calculated in {time.time()-tic:.1f}s")
    return rhumb_route, all_routes



def route_shortest_path(waypoints_df, hour_offset=0, start_date=None, start_time=None, 
                        wind_data_dir=None,gps_bounds=None,
                        max_deg_deviation_from_rhumb=90):
    """
        given a 

    """
    tic = time.time()
    (FCdate, FCtime,_) = get_grib_time(start_date, start_time)
    # calculate bounds
    #bounds = {
    #    'lat': (waypoints_df['lat'].min()-0.25 , waypoints_df['lat'].max()+0.25),
    #    'lng': (waypoints_df['lng'].min()-0.25 , waypoints_df['lng'].max()+0.25),
    #}
    # first leg
    print(f"{waypoints_df.iloc[0]['name']} at {FCdatetime_to_localtime(FCdate, FCtime, hour_offset)}")
    route, sim_t = simulate_shortest_path(
        waypoints_df.iloc[0]['lat'], waypoints_df.iloc[0]['lng'],
        waypoints_df.iloc[1]['lat'], waypoints_df.iloc[1]['lng'],
        simulation_time=hour_offset,
        FCdate=FCdate,
        FCtime=FCtime,
        wind_data_dir=wind_data_dir
        )
    # rest of the legs

    for wp_ndx in range(1,len(waypoints_df)-1):
        print(f"{waypoints_df.iloc[wp_ndx]['name']} at {FCdatetime_to_localtime(FCdate, FCtime, sim_t)}")
        route_t, sim_t = simulate_shortest_path(
            route.iloc[-1]['lat'], route.iloc[-1]['lng'],
            waypoints_df.iloc[wp_ndx+1]['lat'], waypoints_df.iloc[wp_ndx+1]['lng'],
            simulation_time=sim_t,
            FCdate=FCdate,
            FCtime=FCtime,
            wind_data_dir=wind_data_dir
            )
        # append this leg to the route
        route = pandas.concat([route,route_t.iloc[1:]], ignore_index=True)
    # end
    print(f"{waypoints_df.iloc[-1]['name']} at {FCdatetime_to_localtime(FCdate, FCtime, sim_t)}")
    print(f"route calculated in {time.time()-tic:.1f}s")

    return route


def simulate_all_paths(lat,lng, lat_end, lng_end, simulation_time=0, 
                        FCdate=None, FCtime=None, 
                        wind_data_dir=None,
                        gps_bounds=None,
                        max_deg_deviation_from_rhumb=90,
                        max_simulation_time=1000):
    
    traveled_path = []
    traveled_path.append({  #start
            'lat':lat,
            'lng':lng,
            'date': FCdatetime_to_localtime(FCdate, FCtime,simulation_time)
        })

    all_routes = []


    # start recursive process
    take_simulation_step(all_routes, traveled_path, None,
                        max_simulation_time, FCdate, FCtime, simulation_time, 
                        lat, lng,
                        lat, lng, #start
                        lat_end, lng_end,
                        wind_data_dir,
                        gps_bounds, max_deg_deviation_from_rhumb
                        )
    #
    return all_routes



def take_simulation_step(route_storage, past_traveled_path, next_route_step,
                        max_simulation_time,
                        FCdate, FCtime, simulation_time,
                        lat, lng,
                        lat_start, lng_start,
                        lat_end, lng_end,
                        wind_data_dir,
                        gps_bounds=None,
                        max_deg_deviation_from_rhumb=90,
                        ):

    time_step_size = 1 #hour

    # short cuurcit
    if len(route_storage)>10: return

    traveled_path = copy.copy(past_traveled_path)
    if next_route_step is not None:
        traveled_path.append(next_route_step)

        # check if we have reached our destination
        # method: if distance traveled (boat_speed*time_step_size) > dist_to_dest, we have arived
        if( next_route_step['sog'] > next_route_step['dtg'] and \
            haversine_distance(lat,lng, lat_start,lng_start) >= haversine_distance(lat_end,lng_end, lat_start,lng_start)  ):
            route_storage.append(traveled_path)
            print(f"found path of {len(traveled_path)} steps")
            return


    (grib_file_date, grib_file_time, hr_offset) = get_grib_time(FCdate, FCtime, simulation_time)
    wind_data = load_historical_gfs_forecast(wind_data_dir, grib_file_date, 
                                                  grib_file_time, hr_offset)
    (tws, twd) = get_wind_at_location_from_data(wind_data, lat, lng)
    polars = polar_rhiannon(tws)
    for (angle,boat_speed) in polars:
        for delta_angle in (angle, -1*angle):
            boat_mag = (twd+delta_angle)%360
            (dlat,dlng) = calculate_destination_latlng(lat,lng,boat_speed,boat_mag,time_step_size) # hour
            dist_to_dest = haversine_distance(dlat,dlng,lat_end,lng_end)
            # Check to see if we need to prune this path:
            # check the max simulation time
            if simulation_time+1 > max_simulation_time:
                continue # throw away this path
            # check the angle deviation
            if calculate_deviation(lat, lng, lat_end, lng_end, boat_mag) > max_deg_deviation_from_rhumb:
                continue # throw away this path
            # check the bounds
            if gps_bounds is not None:
                [min_lat,max_lat,max_lng,min_lng] = gps_bounds
                if dlat < min_lat or dlat > max_lat or dlng < min_lng or dlng > max_lng:
                    continue #throw away this path
            # take the next step
            next_route_step = {}
            next_route_step['twa']=angle
            next_route_step['mag']=boat_mag
            next_route_step['lat']=dlat
            next_route_step['lng']=dlng
            next_route_step['dtg']=dist_to_dest
            next_route_step['sog']=boat_speed
            next_route_step['date']=FCdatetime_to_localtime(FCdate, FCtime,simulation_time+1)
            #
            take_simulation_step(route_storage, traveled_path, next_route_step,
                        max_simulation_time,
                        FCdate, FCtime, simulation_time+1,
                        dlat, dlng,
                        lat_start, lng_start,
                        lat_end, lng_end,
                        wind_data_dir,
                        gps_bounds,
                        max_deg_deviation_from_rhumb)



#def simulate_shortest_path(lat,lng, lat_end, lng_end, gps_bounds, simulation_time=0, 
#                            FCdate=None, FCtime=None, ):
def simulate_shortest_path(lat,lng, lat_end, lng_end, simulation_time=0, 
                            FCdate=None, FCtime=None, wind_data_dir=None):
    """
    Simulate the sailing of the rhum line path between two points
    """
    if FCdate is None or FCtime is None:
        (FCdate, FCtime,_) = get_grib_time()
    print('starting time:',FCdate, FCtime,FCdatetime_to_localtime(FCdate, FCtime,simulation_time))
    last_dist_togo = haversine_distance(lat,lng,lat_end,lng_end);
    ####
    traveled_path = []
    traveled_path.append({  #start
            'lat':lat,
            'lng':lng,
            'date': FCdatetime_to_localtime(FCdate, FCtime,simulation_time)
        })
    #####
    max_steps = 1000

    for _ in range(0,max_steps): # limit total number of steps
        if wind_data_dir is not None:
            (grib_file_date, grib_file_time, hr_offset) = get_grib_time(FCdate, FCtime, simulation_time)
            wind_data = load_historical_gfs_forecast(wind_data_dir, grib_file_date, 
                                                          grib_file_time, hr_offset)
            (tws, twd) = get_wind_at_location_from_data(wind_data, lat, lng)
        else:
            gps_bounds = {
               'lat': (lat-0.25 , lat+0.25),
               'lng': (lng-0.25 , lng+0.25),
            }
            if simulation_time <= 120:
                grib_file = download_nomads_gfs_forecast_file(FCdate, FCtime, gps_bounds['lat'], gps_bounds['lng'], 
                    simulation_time)
                (tws, twd) = get_wind_at_location_from_grib(grib_file, lat, lng, simulation_time)
            else:
                # for GFS, after 120, they give every 3 hours
                hr3_sim_time = simulation_time-(simulation_time-120)%3
                grib_file = download_nomads_gfs_forecast_file(FCdate, FCtime, gps_bounds['lat'], gps_bounds['lng'], 
                    hr3_sim_time)
                (tws, twd) = get_wind_at_location_from_grib(grib_file, lat, lng, hr3_sim_time)
            
        #print(f"{simulation_time}: ({lat},{lng}) tws={tws} twd={twd}")
        polars = polar_rhiannon(tws)
        # find all possible angles
        best_dist_togo = None
        best_nav_args = {}
        for (angle,boat_speed) in polars:
            for delta_angle in (angle, -1*angle):
                boat_mag = (twd+delta_angle)%360
                (dlat,dlng) = calculate_destination_latlng(lat,lng,boat_speed,boat_mag,1) # hour
                dist_to_dest = haversine_distance(dlat,dlng,lat_end,lng_end)
                #print(f" twa={angle} mag={boat_mag:.1f} dest=({dlat:.1f},{dlng:.1f}) dist_togo={dist_to_dest:.1f}")
                if (best_dist_togo is None or dist_to_dest < best_dist_togo) and \
                    not does_path_cross_boundary(lat,lng,dlat,dlng,shore_boundaries):
                    best_dist_togo = dist_to_dest
                    best_nav_args['twa']=angle
                    best_nav_args['mag']=boat_mag
                    best_nav_args['lat']=dlat
                    best_nav_args['lng']=dlng
                    best_nav_args['dtg']=dist_to_dest
                    best_nav_args['sog']=boat_speed
                    best_nav_args['date']=FCdatetime_to_localtime(FCdate, FCtime,simulation_time+1)
        if best_dist_togo < last_dist_togo:
            print(f"{simulation_time}: twa={best_nav_args['twa']} mag={best_nav_args['mag']:.1f} dtg={best_nav_args['dtg']:.1f} sog={best_nav_args['sog']:.1f}")
            #save and keep going
            traveled_path.append(best_nav_args)
            simulation_time+=1
            lat=best_nav_args['lat']
            lng=best_nav_args['lng']
            last_dist_togo = best_dist_togo
        else:
            # over shot
            break

    return pandas.DataFrame(traveled_path), simulation_time
            
                

def calculate_deviation(lat, lng, dlat, dlng, mag):
    """
    Calculate the deviation from the direct line (great circle bearing) 
    to the destination.

    Args:
        lat (float): Current latitude in degrees.
        lng (float): Current longitude in degrees.
        dlat (float): Destination latitude in degrees.
        dlng (float): Destination longitude in degrees.
        mag (float): Current heading in degrees.

    Returns:
        float: Deviation in degrees (-180 to 180).
    """
    # Convert degrees to radians
    lat = math.radians(lat)
    lng = math.radians(lng)
    dlat = math.radians(dlat)
    dlng = math.radians(dlng)
    
    # Calculate the great circle bearing
    delta_lng = dlng - lng
    y = math.sin(delta_lng) * math.cos(dlat)
    x = math.cos(lat) * math.sin(dlat) - math.sin(lat) * math.cos(dlat) * math.cos(delta_lng)
    bearing = math.atan2(y, x)
    
    # Convert bearing to degrees and normalize to 0–360
    bearing_deg = (math.degrees(bearing) + 360) % 360
    
    # Calculate deviation
    deviation = (mag - bearing_deg + 540) % 360 - 180
    
    return math.fabs(deviation)

def get_grib_time(grib_date=None, grib_time=None, hr_offset=0):
    """
    Calculates the latest GRIB file base time in the format required for downloading.

    Returns:
        str: The latest base time in 'YYYYMMDD/HH' format.
    """
    if grib_date is None or grib_time is None:
        # Get the current UTC time
        now = datetime.datetime.now(datetime.UTC)
        #print(f"Current UTC time: {now.strftime('%c')}")
    else:
        # parse the grib_date/grib_time 
        now = datetime.datetime.strptime(f"{grib_date} {grib_time}:00:00", "%Y%m%d %H:%M:%S")

    if hr_offset is not None:
        now = now + datetime.timedelta(hours=hr_offset)

    # GFS model updates every 6 hours (00, 06, 12, 18 UTC)
    # Find the most recent model run hour
    recent_run_hour = (now.hour // 6) * 6
    recent_run_time = now.replace(hour=recent_run_hour, minute=0, second=0, microsecond=0)

    if grib_date is None or grib_time is None:
        # If the current time is before the most recent run's availability, go back one cycle
        # GFS files are typically available ~4 hours after the run starts
        if now < recent_run_time + datetime.timedelta(hours=4):
            recent_run_time -= datetime.timedelta(hours=6)

    # Format as 'YYYYMMDD/HH'
    return recent_run_time.strftime("%Y%m%d"), recent_run_time.strftime("%H"), math.floor((now-recent_run_time).total_seconds()/3600)


def FCdatetime_to_localtime(FCdate,FCtime, hr_offset=0):
    dt_utc = datetime.datetime.strptime(FCdate + FCtime, "%Y%m%d%H")
    # Add "hr_offset" hours to the datetime
    dt_utc = dt_utc + datetime.timedelta(hours=hr_offset)
    dt_utc = pytz.utc.localize(dt_utc)

    # Convert to the local timezone
    local_tz = pytz.timezone("America/Los_Angeles")  # Replace with your timezone
    dt_local = dt_utc.astimezone(local_tz)
    # Print the result
    #print("Local Time:", dt_local)
    return dt_local

def load_historical_gfs_forecast(wind_data_dir, grib_date, grib_time, hr_offset):
    pkl_file = f"{wind_data_dir}/{grib_date}-{grib_time:02}-gfs.0p25.f{hr_offset:03}.pkl"
    if not os.path.isfile(pkl_file):
        raise Exception(f"PKL file not found:'{pkl_file}'")
    with open(pkl_file, 'rb') as fd:
        wind_data = pickle.load(fd)
    return wind_data


# docs here: https://nomads.ncep.noaa.gov/gribfilter.php?ds=gfs_0p25_1hr

def download_nomads_gfs_forecast_file(grib_date, grib_time, lat_bounds, lng_bounds, simulation_time):
    min_lng = lng_bounds[0] if lng_bounds[0]>0 else lng_bounds[0]+360
    max_lng = lng_bounds[1] if lng_bounds[1]>0 else lng_bounds[1]+360
    #print(min_lng,max_lng)
    min_lat = lat_bounds[0]
    max_lat = lat_bounds[1]
    #https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25_1hr.pl?dir=%2Fgfs.20241203%2F12%2Fatmos&file=gfs.t12z.pgrb2.0p25.f240&var_UGRD=on&var_VGRD=on&lev_10_m_above_ground=on&subregion=&toplat=34.5&leftlon=238&rightlon=244&bottomlat=32
    url = f"https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25_1hr.pl?dir=%2Fgfs.{grib_date}%2F{grib_time}%2Fatmos&file=gfs.t{grib_time}z.pgrb2.0p25.f{simulation_time:03}&var_UGRD=on&var_VGRD=on&lev_10_m_above_ground=on&subregion=&toplat={max_lat}&leftlon={min_lng}&rightlon={max_lng}&bottomlat={min_lat}"
    #print(url)
    output_file = f"grib_files/{grib_date}-{grib_time}-gfs.t{grib_time}z.pgrb2.0p25.f{simulation_time:03}_{max_lat}_{min_lat}_{max_lng}_{min_lng}"
    #print(output_file)

    if os.path.isfile(output_file):
        print(f"Using GRIB2 file: {output_file}")
        return output_file

    
    try:
        # Make the request to download the GRIB2 file
        print(f"Starting download", end=" ")
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Check for HTTP errors
        
        # Save the file locally
        with open(output_file, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        
        print(f"GRIB2 file downloaded: {output_file}")
        return output_file
    except requests.exceptions.RequestException as e:
        print(f"Error downloading GRIB2 file: {e}")
        raise e
    

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance between two points on the Earth in nautical miles.
    
    Parameters:
        lat1 (float): Latitude of the first point in degrees.
        lon1 (float): Longitude of the first point in degrees.
        lat2 (float): Latitude of the second point in degrees.
        lon2 (float): Longitude of the second point in degrees.
    
    Returns:
        float: Distance in nautical miles.
    """
    # Radius of Earth in nautical miles
    R = 3440.065
    
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    # Distance in nautical miles
    distance = R * c
    return distance

def mps_to_knots(speed_mps):
    """
    Convert speed from meters per second (m/s) to knots.

    Parameters:
        speed_mps (float): Speed in meters per second.

    Returns:
        float: Speed in knots.
    """
    # 1 knot = 1.9438444924406 m/s
    knots_per_mps = 1.9438444924406
    return speed_mps * knots_per_mps



def get_wind_at_location_from_data(wind_data, mylat, mylng, verbose=False):

    lats = wind_data['lats']
    lngs = wind_data['lngs']
    v_msg = wind_data['v_msg']
    u_msg = wind_data['u_msg']

    found_lat=False
    found_lng=False
    for lat_ndx in range(0, lats.shape[0]):
        #print(lat_ndx, lats[lat_ndx][0])
        if lats[lat_ndx][0] > mylat:
            found_lat=True
            break
    for lng_ndx in range(0, lngs.shape[1]):
        #print(lng_ndx, lngs[0][lng_ndx])
        if lngs[0][lng_ndx] > mylng: 
            found_lng=True
            break
    if not found_lat or not found_lng:
        raise Exception("could not find index for lat or long")
    ndx_n = lat_ndx
    ndx_s = lat_ndx-1
    ndx_w = lng_ndx
    ndx_e = lng_ndx-1
    d_nw = haversine_distance(mylat,mylng, lats[ndx_n][0], lngs[0][ndx_w])
    d_ne = haversine_distance(mylat,mylng, lats[ndx_n][0], lngs[0][ndx_e])
    d_sw = haversine_distance(mylat,mylng, lats[ndx_s][0], lngs[0][ndx_w])
    d_se = haversine_distance(mylat,mylng, lats[ndx_s][0], lngs[0][ndx_e])
    w_nw = d_nw / (d_nw+d_ne+d_sw+d_se)
    w_ne = d_ne / (d_nw+d_ne+d_sw+d_se)
    w_sw = d_sw / (d_nw+d_ne+d_sw+d_se)
    w_se = d_se / (d_nw+d_ne+d_sw+d_se)
    if verbose:
        print(f"NW: ({lats[ndx_n][0]},{lngs[0][ndx_w]})  d={d_nw} w={w_nw} u={u_msg[ndx_n][ndx_w]} v={v_msg[ndx_n][ndx_w]}")
        print(f"NE: ({lats[ndx_n][0]},{lngs[0][ndx_e]})  d={d_ne} w={w_ne} u={u_msg[ndx_n][ndx_e]} v={v_msg[ndx_n][ndx_e]}")
        print(f"SW: ({lats[ndx_s][0]},{lngs[0][ndx_w]})  d={d_sw} w={w_sw} u={u_msg[ndx_s][ndx_w]} v={v_msg[ndx_s][ndx_w]}")
        print(f"SE: ({lats[ndx_s][0]},{lngs[0][ndx_e]})  d={d_se} w={w_se} u={u_msg[ndx_s][ndx_e]} v={v_msg[ndx_s][ndx_e]}")
    
    v_wind = w_nw * v_msg[ndx_n][ndx_w] \
           + w_ne * v_msg[ndx_n][ndx_e] \
           + w_sw * v_msg[ndx_s][ndx_w] \
           + w_se * v_msg[ndx_s][ndx_e]
    u_wind = w_nw * u_msg[ndx_n][ndx_w] \
           + w_ne * u_msg[ndx_n][ndx_e] \
           + w_sw * u_msg[ndx_s][ndx_w] \
           + w_se * u_msg[ndx_s][ndx_e]            
    
    # Calculate wind speed (m/s->knots) and direction (degrees)
    wind_speed = mps_to_knots( math.sqrt(u_wind**2 + v_wind**2) )
    wind_direction = (270 - math.degrees(math.atan2(v_wind, u_wind))) % 360
    if verbose:
        print(f"Wind: u={u_wind} v={v_wind}")
        print(f"wind_speed {wind_speed}, wind_direction {wind_direction}")
    return (wind_speed, wind_direction)



def get_wind_at_location_from_grib(grib_file, mylat, mylng, simulation_time, verbose=False):
    """
    Extracts wind speed and direction at a given GPS coordinate and time from a GRIB2 file.

    Parameters:
        grib_file (str): Path to the GRIB2 file.
        lat (float): Latitude of the location.
        lng (float): Longitude of the location.
        simulation_time (int): Forecast hour to extract data for.
        verbose (boolean): print debugging info
    Returns:
        dict: A dictionary with wind speed (m/s) and direction (degrees).
    """
    try:
        # Open the GRIB2 file
        with pygrib.open(grib_file) as grbs:
            # Filter messages for U and V wind components at 10m above ground and the given forecast time
            # Extract the data and corresponding lat/lon grid
            u_msg = grbs.select(name="10 metre U wind component", level=10, forecastTime=simulation_time)[0].values
            v_msg = grbs.select(name="10 metre V wind component", level=10, forecastTime=simulation_time)[0].values
            lats, lngs = grbs[1].latlons()


            # Interpolate U and V components at the exact point
            found_lat=False
            found_lng=False
            for lat_ndx in range(0, lats.shape[0]):
                #print(lat_ndx, lats[lat_ndx][0])
                if lats[lat_ndx][0] > mylat:
                    found_lat=True
                    break
            for lng_ndx in range(0, lngs.shape[1]):
                #print(lng_ndx, lngs[0][lng_ndx])
                if lngs[0][lng_ndx] > mylng: 
                    found_lng=True
                    break
            if not found_lat or not found_lng:
                raise Exception("could not find index for lat or long")
            ndx_n = lat_ndx
            ndx_s = lat_ndx-1
            ndx_w = lng_ndx
            ndx_e = lng_ndx-1
            d_nw = haversine_distance(mylat,mylng, lats[ndx_n][0], lngs[0][ndx_w])
            d_ne = haversine_distance(mylat,mylng, lats[ndx_n][0], lngs[0][ndx_e])
            d_sw = haversine_distance(mylat,mylng, lats[ndx_s][0], lngs[0][ndx_w])
            d_se = haversine_distance(mylat,mylng, lats[ndx_s][0], lngs[0][ndx_e])
            w_nw = d_nw / (d_nw+d_ne+d_sw+d_se)
            w_ne = d_ne / (d_nw+d_ne+d_sw+d_se)
            w_sw = d_sw / (d_nw+d_ne+d_sw+d_se)
            w_se = d_se / (d_nw+d_ne+d_sw+d_se)
            if verbose:
                print(f"NW: ({lats[ndx_n][0]},{lngs[0][ndx_w]})  d={d_nw} w={w_nw} u={u_msg[ndx_n][ndx_w]} v={v_msg[ndx_n][ndx_w]}")
                print(f"NE: ({lats[ndx_n][0]},{lngs[0][ndx_e]})  d={d_ne} w={w_ne} u={u_msg[ndx_n][ndx_e]} v={v_msg[ndx_n][ndx_e]}")
                print(f"SW: ({lats[ndx_s][0]},{lngs[0][ndx_w]})  d={d_sw} w={w_sw} u={u_msg[ndx_s][ndx_w]} v={v_msg[ndx_s][ndx_w]}")
                print(f"SE: ({lats[ndx_s][0]},{lngs[0][ndx_e]})  d={d_se} w={w_se} u={u_msg[ndx_s][ndx_e]} v={v_msg[ndx_s][ndx_e]}")
            
            v_wind = w_nw * v_msg[ndx_n][ndx_w] \
                   + w_ne * v_msg[ndx_n][ndx_e] \
                   + w_sw * v_msg[ndx_s][ndx_w] \
                   + w_se * v_msg[ndx_s][ndx_e]
            u_wind = w_nw * u_msg[ndx_n][ndx_w] \
                   + w_ne * u_msg[ndx_n][ndx_e] \
                   + w_sw * u_msg[ndx_s][ndx_w] \
                   + w_se * u_msg[ndx_s][ndx_e]            
            
            # Calculate wind speed (m/s->knots) and direction (degrees)
            wind_speed = mps_to_knots( math.sqrt(u_wind**2 + v_wind**2) )
            wind_direction = (270 - math.degrees(math.atan2(v_wind, u_wind))) % 360
            if verbose:
                print(f"Wind: u={u_wind} v={v_wind}")
                print(f"wind_speed {wind_speed}, wind_direction {wind_direction}")
            return (wind_speed, wind_direction)

    except Exception as e:
        print(f"Error processing GRIB2 file: {e}")
        return None



def polar_rhiannon(wind_speed):
    """
    Return list of (angle, boat_speed) pairs for a given input wind_speed
    """
    angles = [52,60,75,90,110,120,135,150,165,180]
    
    tws = [6 ,  8 , 10 ,    12 ,    16 ,    20 ,    24] #    'True wind speed':,
    
    data = {
    'Optimum Beat':[(48.2,3.87),(46.9,4.85),(45.8,5.44),(44.8,6.13),(43.4,6.6),(41.9,6.77),(41.8,6.87)],
    'Optimum Run':[(132.2,4.68),(139.1,5.33),(149.5,5.61),(151.4,6.32),(163.7,7.09),(170.7,7.73),(172.3,8.31)],
    '52-degrees':[  4.17,   5.3,    6.09,   6.72,   7.26,   7.48,   7.57],
    '60-degrees':[  4.68,   5.79,   6.67,   7.17,   7.64,   7.85,   7.97],
    '75-degrees':[  5.63,   6.85,   7.5,    7.83,   8.23,   8.47,   8.61],
    '90-degrees':[  6.04,   7.21,   7.81,   8.17,   8.6,    8.89,   9.1],
    '110-degrees':[ 5.95,   7.14,   7.73,   8.15,   8.81,   9.29,   9.57],
    '120-degrees':[ 5.62,   6.77,   7.45,   7.88,   8.57,   9.19,   9.75],
    '135-degrees':[ 4.44,   5.66,   6.59,   7.28,   8.1,    8.74,   9.36],
    '150-degrees':[ 3.45,   4.57,   5.58,   6.4,    7.59,   8.29,   8.88],
    '165-degrees':[ 2.9,    3.88,   4.81,   5.66,   7.04,   7.87,   8.47],
    '180-degrees':[ 2.61,   3.52,   4.39,   5.2,    6.59,   7.56,   8.18],
    }
    for ndx in range(len(tws)):
        if tws[ndx] > wind_speed: break
    ndx-=1 #ndx of speed less than wind speed
    #print('ndx',ndx)

    polars = []
    # beat
    if ndx==-1:
        ta = data['Optimum Beat'][0][0]
        ts = data['Optimum Beat'][0][1] * (wind_speed/tws[0])
        polars.append( (ta,ts) )
    else:
        polars.append( data['Optimum Beat'][ndx] )
    # run through angles
    for angle in angles:
        if ndx==-1:
            ts = data[f"{angle}-degrees"][0] * (wind_speed/tws[0])
            polars.append( (angle,ts) )
        else:
            polars.append( (angle, data[f"{angle}-degrees"][ndx]) )
    # run
    if ndx==-1:
        ta = data['Optimum Run'][0][0]
        ts = data['Optimum Run'][0][1] * (wind_speed/tws[0])
        polars.append( (ta,ts) )
    else:
        polars.append( data['Optimum Run'][ndx] )

    # return pairs of (angle, boat_speed)
    return polars

def calculate_destination_latlng(lat, lon, speed_knots, direction, travel_time_hours):
    """
    Calculate the destination latitude and longitude.

    Parameters:
        lat (float): Starting latitude in decimal degrees.
        lon (float): Starting longitude in decimal degrees.
        speed_knots (float): Speed in knots.
        direction (float): Direction in degrees (0° is North, 90° is East).
        travel_time_hours (float): Travel time in hours.

    Returns:
        tuple: (destination_lat, destination_lon) in decimal degrees.
    """
    # Convert speed from knots to nautical miles per hour (1 knot = 1 nautical mile per hour)
    distance_nm = speed_knots * travel_time_hours
    
    # Earth's radius in nautical miles
    R = 3440.065
    
    # Convert inputs to radians
    lat = math.radians(lat)
    lon = math.radians(lon)
    direction = math.radians(direction)
    
    # Calculate the destination latitude
    destination_lat = math.asin(
        math.sin(lat) * math.cos(distance_nm / R) +
        math.cos(lat) * math.sin(distance_nm / R) * math.cos(direction)
    )
    
    # Calculate the destination longitude
    destination_lon = lon + math.atan2(
        math.sin(direction) * math.sin(distance_nm / R) * math.cos(lat),
        math.cos(distance_nm / R) - math.sin(lat) * math.sin(destination_lat)
    )
    
    # Convert the results back to degrees
    destination_lat = math.degrees(destination_lat)
    destination_lon = math.degrees(destination_lon)
    
    # Normalize longitude to be within the range [-180, 180]
    destination_lon = (destination_lon + 180) % 360 - 180
    
    return destination_lat, destination_lon



def get_parent_isochron_routes(isochron, lat, lng):
    parent_routes = []
    for route in isochron:
        if route[-1]['lat']==lat and route[-1]['lng']==lng: continue # skip the path you took, it will always intersect
        parent_routes.append(((route[-2]['lat'],route[-2]['lng']),(route[-1]['lat'],route[-1]['lng'])))
    return parent_routes

def does_path_cross_parent_path(lat,lng, dlat, dlng, parent_isochron_routes):
    # Check intersection with each boundary segment
    for route in parent_isochron_routes:
        if lines_intersect((lat, lng), (dlat, dlng), route[0], route[1]):
            return True
    return False

def does_path_cross_boundary(lat, lng, dlat, dlng, boundaries):
    """
    Check if the path from (lat, lng) to (dlat, dlng) crosses a boundary.

    Args:
        lat (float): Current latitude.
        lng (float): Current longitude.
        dlat (float): Destination latitude.
        dlng (float): Destination longitude.
        boundaries (list of lists of tuples): List of Lists of (latitude, longitude) 
            pairs defining the boundary.

    Returns:
        bool: True if the path crosses the boundary, False otherwise.
    """


    # Current path as a segment
    current_path = ((lat, lng), (dlat, dlng))
    #print(f"current_path={current_path}")

    # Check intersection with each boundary segment
    for boundary in boundaries:
        #print(f"boundary={boundary}")
        for i in range(len(boundary) - 1):
            boundary_segment = (boundary[i], boundary[i + 1])
            #print(f"   boundary_segment={boundary_segment}")
            if lines_intersect(current_path[0], current_path[1], boundary_segment[0], boundary_segment[1]):
                return True

    return False



def ccw_crossprod_normalized(p1, p2, p3):
    """Compute the cross product of the angle formed between normalized vectors p1-p2 and p2-p3."""
    # Compute vectors
    v1 = (p2[0] - p1[0], p2[1] - p1[1])
    v2 = (p3[0] - p2[0], p3[1] - p2[1])
    
    # Normalize vectors
    mag_v1 = math.sqrt(v1[0]**2 + v1[1]**2)
    mag_v2 = math.sqrt(v2[0]**2 + v2[1]**2)
    if mag_v1 == 0 or mag_v2 == 0:
        return 0
        #raise ValueError("Cannot normalize a zero-length vector.")
    
    v1_normalized = (v1[0] / mag_v1, v1[1] / mag_v1)
    v2_normalized = (v2[0] / mag_v2, v2[1] / mag_v2)
    
    # Compute cross product of normalized vectors
    return v1_normalized[0] * v2_normalized[1] - v1_normalized[1] * v2_normalized[0]

def ccw_crossprod(p1, p2, p3):
    """ compute the cross product of the angle formed between p1-p2 and p2-p3"""
    return (p2[0]-p1[0])*(p3[1]-p1[1]) - (p2[1]-p1[1])*(p3[0]-p1[0])

def is_ccw(p1, p2, p3):
    a = ccw_crossprod(p1, p2, p3)
    if a>0: return -1
    if a<0: return 1
    return 0


def lines_intersect(p1, p2, q1, q2):
    """Check if two line segments (p1-p2 and q1-q2) intersect."""
    def orientation(a, b, c):
        """Find orientation of the triplet (a, b, c)."""
        val = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
        #print(f"orientation({a}, {b}, {c}) val={val}")
        if val == 0:
            return 0  # Collinear
        return 1 if val > 0 else -1  # Clockwise or counterclockwise

    def on_segment(a, b, c):
        """Check if point b lies on segment a-c."""
        return (min(a[0], c[0]) <= b[0] <= max(a[0], c[0]) and
                min(a[1], c[1]) <= b[1] <= max(a[1], c[1]))

    o1 = orientation(p1, p2, q1)
    o2 = orientation(p1, p2, q2)
    o3 = orientation(q1, q2, p1)
    o4 = orientation(q1, q2, p2)

    #print(f"o1={o1} o2={o2} o3={o3} o4={o4}")

    # General case
    if o1 != o2 and o3 != o4:
        return True

    # Special cases
    if o1 == 0 and on_segment(p1, q1, p2): return True
    if o2 == 0 and on_segment(p1, q2, p2): return True
    if o3 == 0 and on_segment(q1, p1, q2): return True
    if o4 == 0 and on_segment(q1, p2, q2): return True

    return False