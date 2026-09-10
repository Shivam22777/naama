from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
import json
import math

from tracker.models import Route, BusStop, Driver, Passenger, Trip, TripStopEvent

def get_current_driver(request):
    driver_id = request.session.get('driver_id')
    if driver_id:
        try:
            return Driver.objects.get(id=driver_id)
        except Driver.DoesNotExist:
            pass
    return None

def get_current_passenger(request):
    user_id = request.session.get('user_id')
    if user_id:
        try:
            return Passenger.objects.get(id=user_id)
        except Passenger.DoesNotExist:
            pass
    return None

def home(request):
    driver = get_current_driver(request)
    passenger = get_current_passenger(request)
    return render(request, 'home.html', {
        'driver': driver,
        'passenger': passenger,
    })

# --- DRIVER AUTH & DASHBOARD ---

def driver_register(request):
    routes = Route.objects.all().order_by('route_id')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()
        bus_number = request.POST.get('bus_number', '').strip()
        route_id = request.POST.get('route_id')
        start_stop_id = request.POST.get('start_stop_id')
        dest_stop_id = request.POST.get('dest_stop_id')

        if not name or not phone or not password or not bus_number or not route_id or not start_stop_id or not dest_stop_id:
            messages.error(request, "All driver profile fields are required.")
            return render(request, 'driver_register.html', {'routes': routes})

        if Driver.objects.filter(phone_number=phone).exists():
            messages.error(request, "Driver with this phone number already registered. Please login.")
            return redirect('driver_login')

        route = get_object_or_404(Route, route_id=route_id)
        start_stop = get_object_or_404(BusStop, id=start_stop_id, route=route)
        dest_stop = get_object_or_404(BusStop, id=dest_stop_id, route=route)

        driver = Driver.objects.create(
            name=name,
            phone_number=phone,
            password=make_password(password),
            bus_number=bus_number,
            route=route,
            start_stop=start_stop,
            destination_stop=dest_stop
        )
        request.session['driver_id'] = driver.id
        messages.success(request, f"Welcome {driver.name}! Driver profile created successfully.")
        return redirect('driver_dashboard')

    return render(request, 'driver_register.html', {'routes': routes})

def driver_login(request):
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()

        try:
            driver = Driver.objects.get(phone_number=phone)
            if check_password(password, driver.password):
                request.session['driver_id'] = driver.id
                messages.success(request, f"Welcome back, {driver.name}!")
                return redirect('driver_dashboard')
            else:
                messages.error(request, "Invalid password.")
        except Driver.DoesNotExist:
            messages.error(request, "No driver account found with this phone number.")

    return render(request, 'driver_login.html')

def driver_logout(request):
    request.session.pop('driver_id', None)
    messages.info(request, "Driver logged out.")
    return redirect('home')

def driver_dashboard(request):
    driver = get_current_driver(request)
    if not driver:
        messages.error(request, "Please login as driver to access dashboard.")
        return redirect('driver_login')

    # Check for active trip (LIVE, STOPPED, DELAYED)
    active_trip = Trip.objects.filter(driver=driver, status__in=['LIVE', 'STOPPED', 'DELAYED']).first()

    # Recent trip history
    recent_trips = Trip.objects.filter(driver=driver).order_by('-started_at')[:10]

    # Check if stationary >= 10 minutes
    is_stopped_long = False
    if active_trip and active_trip.stopped_since:
        duration = timezone.now() - active_trip.stopped_since
        if duration >= timedelta(minutes=10):
            is_stopped_long = True

    return render(request, 'driver_dashboard.html', {
        'driver': driver,
        'active_trip': active_trip,
        'recent_trips': recent_trips,
        'is_stopped_long': is_stopped_long,
        'routing_api_key_available': bool(getattr(settings, 'ROUTING_API_KEY', '')),
    })

# --- PASSENGER AUTH & DASHBOARD ---

def user_register(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()

        if not name or not phone or not password:
            messages.error(request, "All fields are required.")
            return render(request, 'user_register.html')

        if Passenger.objects.filter(phone_number=phone).exists():
            messages.error(request, "Passenger with this phone number already registered. Please login.")
            return redirect('user_login')

        passenger = Passenger.objects.create(
            name=name,
            phone_number=phone,
            password=make_password(password)
        )
        request.session['user_id'] = passenger.id
        messages.success(request, f"Welcome {passenger.name}! Account registered successfully.")
        return redirect('user_dashboard')

    return render(request, 'user_register.html')

def user_login(request):
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()

        try:
            passenger = Passenger.objects.get(phone_number=phone)
            if check_password(password, passenger.password):
                request.session['user_id'] = passenger.id
                messages.success(request, f"Welcome back, {passenger.name}!")
                return redirect('user_dashboard')
            else:
                messages.error(request, "Invalid password.")
        except Passenger.DoesNotExist:
            messages.error(request, "No passenger account found with this phone number.")

    return render(request, 'user_login.html')

def user_logout(request):
    request.session.pop('user_id', None)
    messages.info(request, "Passenger logged out.")
    return redirect('home')

def user_dashboard(request):
    passenger = get_current_passenger(request)
    if not passenger:
        messages.error(request, "Please login as passenger to access dashboard.")
        return redirect('user_login')

    stop_names = BusStop.objects.values_list('stop_village_name', flat=True).distinct().order_by('stop_village_name')

    return render(request, 'user_dashboard.html', {
        'passenger': passenger,
        'stop_names': stop_names,
    })

# --- TRIP & GPS APIS ---

def api_get_route_stops(request, route_id):
    stops = BusStop.objects.filter(route_id=route_id).order_by('stop_seq')
    data = [{
        'id': s.id,
        'stop_seq': s.stop_seq,
        'stop_village_name': s.stop_village_name,
        'district': s.district,
        'taluk': s.taluk,
        'cumulative_dist_km': s.cumulative_dist_km,
        'cumulative_travel_time_min': s.cumulative_travel_time_min,
        'stop_dwell_min': s.stop_dwell_min,
        'latitude': s.latitude,
        'longitude': s.longitude,
    } for s in stops]
    return JsonResponse({'stops': data})

@csrf_exempt
def api_start_journey(request):
    """ Requires explicit Real GPS location from driver device """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=400)

    driver = get_current_driver(request)
    if not driver:
        return JsonResponse({'success': False, 'error': 'Driver login required'}, status=403)

    if not driver.route or not driver.start_stop or not driver.destination_stop:
        return JsonResponse({'success': False, 'error': 'Driver profile missing route or stop details'}, status=400)

    # Check if driver already has an active trip
    existing_trip = Trip.objects.filter(driver=driver, status__in=['LIVE', 'STOPPED', 'DELAYED']).first()
    if existing_trip:
        return JsonResponse({'success': True, 'trip_id': existing_trip.id, 'message': 'Existing active trip found.'})

    lat = request.POST.get('latitude')
    lon = request.POST.get('longitude')
    accuracy = request.POST.get('accuracy')

    if not lat or not lon:
        try:
            body_data = json.loads(request.body.decode('utf-8'))
            lat = body_data.get('latitude')
            lon = body_data.get('longitude')
            accuracy = body_data.get('accuracy')
        except Exception:
            pass

    if not lat or not lon:
        return JsonResponse({'success': False, 'error': 'Location permission is required to start live journey. Please enable GPS access.'}, status=400)

    trip = Trip.objects.create(
        driver=driver,
        bus_number=driver.bus_number,
        route=driver.route,
        start_stop=driver.start_stop,
        destination_stop=driver.destination_stop,
        current_latitude=float(lat),
        current_longitude=float(lon),
        current_stop_seq=driver.start_stop.stop_seq,
        status='LIVE'
    )

    return JsonResponse({
        'success': True,
        'trip_id': trip.id,
        'latitude': trip.current_latitude,
        'longitude': trip.current_longitude,
        'accuracy': float(accuracy) if accuracy else None
    })

@csrf_exempt
def api_end_journey(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    driver = get_current_driver(request)
    if not driver:
        return JsonResponse({'error': 'Driver login required'}, status=403)

    trip_id = request.POST.get('trip_id')
    trip = get_object_or_404(Trip, id=trip_id, driver=driver)
    
    trip.status = 'ENDED'
    trip.ended_at = timezone.now()
    trip.save()

    return JsonResponse({'success': True, 'message': 'Trip ended successfully and saved to history.'})

@csrf_exempt
def api_update_location(request):
    """ Real GPS update endpoint """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=400)

    driver = get_current_driver(request)
    if not driver:
        return JsonResponse({'success': False, 'error': 'Driver login required'}, status=403)

    lat = request.POST.get('latitude')
    lon = request.POST.get('longitude')
    accuracy = request.POST.get('accuracy')
    trip_id = request.POST.get('trip_id')

    if not lat or not lon:
        try:
            body_data = json.loads(request.body.decode('utf-8'))
            lat = body_data.get('latitude')
            lon = body_data.get('longitude')
            accuracy = body_data.get('accuracy')
            if not trip_id:
                trip_id = body_data.get('trip_id')
        except Exception:
            pass

    if trip_id:
        trip = Trip.objects.filter(id=trip_id, driver=driver).first()
    else:
        trip = Trip.objects.filter(driver=driver, status__in=['LIVE', 'STOPPED', 'DELAYED']).first()

    if not trip:
        return JsonResponse({'success': False, 'error': 'No active trip'}, status=400)

    if trip.status == 'ENDED':
        return JsonResponse({'success': False, 'error': 'Trip has already ended'}, status=400)

    if lat and lon:
        new_lat = float(lat)
        new_lon = float(lon)

        # Distance calculation to detect stationary state
        if trip.current_latitude and trip.current_longitude:
            dist_km = math.sqrt((new_lat - trip.current_latitude)**2 + (new_lon - trip.current_longitude)**2) * 111.0
            if dist_km < 0.05: # Stationary (< 50 meters)
                if not trip.stopped_since:
                    trip.stopped_since = timezone.now()
            else:
                # Bus is moving!
                if trip.status in ['STOPPED', 'DELAYED']:
                    trip.status = 'LIVE'
                trip.stopped_since = None
                trip.stop_reason = None

        trip.current_latitude = new_lat
        trip.current_longitude = new_lon

        # Update current stop sequence based on closest route stop
        stops = trip.route.stops.filter(latitude__isnull=False, longitude__isnull=False)
        closest_stop = None
        min_dist = float('inf')
        for s in stops:
            d = math.sqrt((new_lat - s.latitude)**2 + (new_lon - s.longitude)**2)
            if d < min_dist:
                min_dist = d
                closest_stop = s
        
        if closest_stop and closest_stop.stop_seq >= trip.current_stop_seq:
            trip.current_stop_seq = closest_stop.stop_seq

    trip.save()

    # Check if stationary >= 10 min
    is_stopped_long = False
    if trip.stopped_since:
        duration = timezone.now() - trip.stopped_since
        if duration >= timedelta(minutes=10):
            is_stopped_long = True

    return JsonResponse({
        'success': True,
        'latitude': trip.current_latitude,
        'longitude': trip.current_longitude,
        'accuracy': float(accuracy) if accuracy else None,
        'is_stopped_long': is_stopped_long,
        'current_status': trip.status,
        'stop_reason': trip.stop_reason
    })

@csrf_exempt
def api_report_stop_reason(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    driver = get_current_driver(request)
    if not driver:
        return JsonResponse({'error': 'Driver login required'}, status=403)

    trip_id = request.POST.get('trip_id')
    reason = request.POST.get('reason', '').strip()

    trip = get_object_or_404(Trip, id=trip_id, driver=driver)
    trip.stop_reason = reason
    trip.status = 'DELAYED'
    trip.save()

    # Log TripStopEvent
    TripStopEvent.objects.create(
        trip=trip,
        reason=reason,
        latitude=trip.current_latitude,
        longitude=trip.current_longitude
    )

    return JsonResponse({'success': True, 'status': trip.status, 'reason': trip.stop_reason})

@csrf_exempt
def api_resume_journey(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    driver = get_current_driver(request)
    if not driver:
        return JsonResponse({'error': 'Driver login required'}, status=403)

    trip_id = request.POST.get('trip_id')
    trip = get_object_or_404(Trip, id=trip_id, driver=driver)
    trip.stopped_since = None
    trip.stop_reason = None
    trip.status = 'LIVE'
    trip.save()

    # Mark active stop event resolved
    active_event = trip.stop_events.filter(resolved_at__isnull=True).last()
    if active_event:
        active_event.resolved_at = timezone.now()
        active_event.save()

    return JsonResponse({'success': True, 'status': trip.status})

def api_bus_location(request, bus_id):
    """ Read live details from active Trip """
    trip = get_object_or_404(Trip, id=bus_id)
    route_stops = trip.route.stops.order_by('stop_seq')

    curr_stop = route_stops.filter(stop_seq=trip.current_stop_seq).first()
    next_stop = route_stops.filter(stop_seq__gt=trip.current_stop_seq).first()

    seconds_ago = (timezone.now() - trip.last_location_update).total_seconds()
    last_updated_str = f"{int(seconds_ago)}s ago" if seconds_ago < 60 else f"{int(seconds_ago // 60)}m ago"

    stops_data = [{
        'stop_seq': s.stop_seq,
        'stop_village_name': s.stop_village_name,
        'district': s.district,
        'cum_dist_km': s.cumulative_dist_km,
        'cum_time_min': s.cumulative_travel_time_min,
        'latitude': s.latitude,
        'longitude': s.longitude
    } for s in route_stops]

    return JsonResponse({
        'trip_id': trip.id,
        'bus_number': trip.bus_number,
        'route_id': trip.route.route_id,
        'route_name': trip.route.route_name,
        'service_type': trip.route.service_type,
        'status': trip.status,
        'latitude': trip.current_latitude,
        'longitude': trip.current_longitude,
        'current_stop_seq': trip.current_stop_seq,
        'current_stop_name': curr_stop.stop_village_name if curr_stop else "En route",
        'next_stop_name': next_stop.stop_village_name if next_stop else "Destination reached",
        'stop_reason': trip.stop_reason,
        'last_updated': last_updated_str,
        'stops': stops_data,
    })

def api_get_valid_destinations(request):
    """ Returns valid destination stations for selected source station based on dataset stop sequences """
    source_name = request.GET.get('source', '').strip()
    if not source_name:
        return JsonResponse({'destinations': []})

    # Find all stop records matching the source name
    source_stops = BusStop.objects.filter(stop_village_name=source_name)

    valid_dest_set = set()
    for s_stop in source_stops:
        # Find stops on the same route where stop_seq > s_stop.stop_seq
        later_stops = BusStop.objects.filter(route=s_stop.route, stop_seq__gt=s_stop.stop_seq)
        for l_stop in later_stops:
            valid_dest_set.add(l_stop.stop_village_name)

    destinations = sorted(list(valid_dest_set))
    return JsonResponse({'destinations': destinations})

def api_search_buses(request):
    source_name = request.GET.get('source', '').strip()
    dest_name = request.GET.get('destination', '').strip()

    if not source_name or not dest_name:
        return JsonResponse({'error': 'Source and destination stops required'}, status=400)

    if source_name == dest_name:
        return JsonResponse({'error': 'Source and destination cannot be the same'}, status=400)

    source_stops = BusStop.objects.filter(stop_village_name=source_name)
    dest_stops = BusStop.objects.filter(stop_village_name=dest_name)

    # Validate that source -> dest sequence exists on at least one route in dataset
    valid_route_exists = False
    for s in source_stops:
        for d in dest_stops:
            if s.route == d.route and s.stop_seq < d.stop_seq:
                valid_route_exists = True
                break
        if valid_route_exists:
            break

    if not valid_route_exists:
        return JsonResponse({'error': 'Invalid route sequence according to dataset.'}, status=400)

    matching_buses = []

    for s_stop in source_stops:
        for d_stop in dest_stops:
            if s_stop.route == d_stop.route and s_stop.stop_seq < d_stop.stop_seq:
                route = s_stop.route
                # Find active trips on this route (LIVE, STOPPED, DELAYED)
                active_trips = Trip.objects.filter(route=route, status__in=['LIVE', 'STOPPED', 'DELAYED'])

                for t in active_trips:
                    if t.current_stop_seq <= d_stop.stop_seq:
                        curr_stop = route.stops.filter(stop_seq=t.current_stop_seq).first()
                        next_stop = route.stops.filter(stop_seq__gt=t.current_stop_seq).first()

                        if t.current_stop_seq <= s_stop.stop_seq:
                            travel_time_to_source = s_stop.cumulative_travel_time_min - (curr_stop.cumulative_travel_time_min if curr_stop else 0)
                            eta_source_min = max(0, travel_time_to_source)
                        else:
                            eta_source_min = 0

                        travel_time_to_dest = d_stop.cumulative_travel_time_min - (curr_stop.cumulative_travel_time_min if curr_stop else 0)
                        eta_dest_min = max(0, travel_time_to_dest)

                        dist_to_source = max(0.0, round(s_stop.cumulative_dist_km - (curr_stop.cumulative_dist_km if curr_stop else 0.0), 2))

                        matching_buses.append({
                            'trip_id': t.id,
                            'bus_id': t.id,
                            'bus_number': t.bus_number,
                            'driver_name': t.driver.name,
                            'route_id': route.route_id,
                            'route_name': route.route_name,
                            'service_type': route.service_type,
                            'status': t.status,
                            'current_stop_name': curr_stop.stop_village_name if curr_stop else "En route",
                            'next_stop_name': next_stop.stop_village_name if next_stop else d_stop.stop_village_name,
                            'passenger_source': s_stop.stop_village_name,
                            'passenger_dest': d_stop.stop_village_name,
                            'dist_to_source_km': dist_to_source,
                            'eta_source_min': eta_source_min,
                            'eta_dest_min': eta_dest_min,
                            'stop_reason': t.stop_reason,
                            'is_delayed': t.status in ['STOPPED', 'DELAYED'],
                            'latitude': t.current_latitude,
                            'longitude': t.current_longitude,
                        })

    return JsonResponse({'buses': matching_buses})
