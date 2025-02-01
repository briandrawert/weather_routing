import weather_routing
import pandas

def plot_route(route, map_center_lat=33.6, map_center_lng=-118.4, map_zoom=10, color='red'):
    import plotly.graph_objects as go
    import plotly.express as px

    # Create the figure
    fig = go.Figure()

    # Add the first route (red line)
    fig.add_trace(go.Scattermapbox(
        lat=route['lat'],
        lon=route['lng'],
        mode='lines',
        line=dict(color=color, width=2),
        name='Route',
        hovertext=route['date']
    ))
    # Update layout for the map
    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_zoom=map_zoom,
        mapbox_center={"lat":map_center_lat , "lon": map_center_lng},
        margin={"r":0, "t":0, "l":0, "b":0},
       # width=800,
        height=600
    )

    # Show the plot
    fig.show()

def plot_isochron_routes(isochrons=None, waypoints=None,rhumb_route=None, min_route=None, saved_isochrons=None, show_shore_boundaries=False):
    import plotly.graph_objects as go
    import plotly.express as px
    # Create the figure
    fig = go.Figure()
    
    if isochrons is not None:
        for t,isochron in enumerate(isochrons):
            isochron_lats = []
            isochron_lngs = []
            for route in isochron:
                isochron_lats.append(route[-1]['lat'])
                isochron_lngs.append(route[-1]['lng'])
                if t>0:
                    # # Add the first route (red line)
                    fig.add_trace(go.Scattermapbox(
                        lat=[route[-2]['lat'], route[-1]['lat']],
                        lon=[route[-2]['lng'], route[-1]['lng']],
                        mode='lines',
                        line=dict(color='rgba(255, 0, 0, 0.25)', width=2),
                        hovertext=f"{route[-1]['date']}"
                    ))
                    # Add start and end points
                    fig.add_trace(go.Scattermapbox(
                        lat=[route[-2]['lat'], route[-1]['lat']],
                        lon=[route[-2]['lng'], route[-1]['lng']],
                        mode='markers',
                        marker=dict(size=8, color=['black', 'grey']),  
                    ))
            isochron_color = 'rgba(255, 165, 0, 0.75)'
            if t % 2 == 0: isochron_color = 'rgba(165, 255, 0, 0.75)'
            fig.add_trace(go.Scattermapbox(
                lat=isochron_lats,
                lon=isochron_lngs,
                mode='lines',
                line=dict(color=isochron_color, width=2),
                hovertext=f"isochron={t+1}"
            ))

    if saved_isochrons is not None:
        for t,isochron in enumerate(saved_isochrons):
            isochron_lats = []
            isochron_lngs = []
            for route in isochron:
                isochron_lats.append(route[-1]['lat'])
                isochron_lngs.append(route[-1]['lng'])
                if t>0:
                    # # Add the first route (red line)
                    fig.add_trace(go.Scattermapbox(
                        lat=[route[-2]['lat'], route[-1]['lat']],
                        lon=[route[-2]['lng'], route[-1]['lng']],
                        mode='lines',
                        line=dict(color='rgba(0, 0, 0, 0.25)', width=2),
                        hovertext=f"{route[-1]['date']}"
                    ))
            fig.add_trace(go.Scattermapbox(
                lat=isochron_lats,
                lon=isochron_lngs,
                mode='lines',
                line=dict(color='rgba(0, 0, 0, 0.75)', width=2),
                hovertext=f"isochron={t+1}"
            ))
    
    if rhumb_route is not None:
        fig.add_trace(go.Scattermapbox(
            lat=rhumb_route['lat'],
            lon=rhumb_route['lng'],
            mode='lines',
            line=dict(color='blue', width=2),
            hovertext=rhumb_route['date']
        ))
    
    if min_route is not None:
        min_route_dt = pandas.DataFrame(min_route)
        fig.add_trace(go.Scattermapbox(
            lat=min_route_dt['lat'],
            lon=min_route_dt['lng'],
            mode='lines',
            line=dict(color='black', width=2),
            hovertext=min_route_dt['date']
        ))
    

    if waypoints is not None:  
        # Add scatter points for waypoints
        scatter_points = px.scatter_mapbox(waypoints, 
                                           lat="lat", 
                                           lon="lng", 
                                           hover_name="name")
        fig.add_traces(scatter_points.data)


    if show_shore_boundaries:
        # Add the shore boundary line to the figure
        for shore_boundary in weather_routing.shore_boundaries:
            boundary_lat, boundary_lon = zip(*shore_boundary)
            fig.add_trace(go.Scattermapbox(
                lat=boundary_lat,
                lon=boundary_lon,
                mode='lines',
                line=dict(color='green', width=2),
                #name='Boundary'  # Legend label
            ))

    # Update layout for the map
    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_zoom=9,
        mapbox_center={"lat": 33.7, "lon": -118.5},
        margin={"r":0, "t":0, "l":0, "b":0},
       # width=800,
        height=600,
        showlegend=False
    )
    # Show the plot
    fig.show()