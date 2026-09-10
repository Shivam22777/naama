/* ==========================================================================
   NAMMA SARTHI — REAL GPS ENGINE & LEAFLET MAP CONTROLLER
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    startLiveClock();
    initDriverDashboardControls();
    initPassengerDashboard();
});

function format12HourTime(date) {
    let hours = date.getHours();
    let minutes = date.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12;
    minutes = minutes < 10 ? '0' + minutes : minutes;
    return `${hours}:${minutes} ${ampm}`;
}

function calculateArrivalTime(minutesToAdd) {
    if (minutesToAdd === null || minutesToAdd === undefined || isNaN(minutesToAdd)) {
        return null;
    }
    if (minutesToAdd <= 0) {
        return null;
    }
    const now = new Date();
    const arrivalDate = new Date(now.getTime() + minutesToAdd * 60000);
    return format12HourTime(arrivalDate);
}

function startLiveClock() {
    function updateClock() {
        const now = new Date();
        const clockElem = document.getElementById('live-current-clock');
        if (clockElem) {
            clockElem.textContent = format12HourTime(now);
        }
    }
    updateClock();
    setInterval(updateClock, 1000);
}

function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    if (input && input.value) return input.value;
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
}

/* ==========================================================================
   1. DRIVER DASHBOARD: 100% REAL GPS ENGINE (getCurrentPosition + watchPosition)
   ========================================================================== */
function initDriverDashboardControls() {
    const btnStart = document.getElementById('btn-start-journey');
    const gpsPermissionAlert = document.getElementById('gps-permission-alert');
    const gpsStatusText = document.getElementById('gps-status-text');

    const activeTripSection = document.querySelector('.active-journey-section');
    const btnEnd = document.getElementById('btn-end-journey');
    const btnResume = document.getElementById('btn-resume-journey');
    const stoppageAlertCard = document.getElementById('stoppage-alert-card');

    const btnToggleDebug = document.getElementById('btn-toggle-gps-debug');
    const gpsDebugPanel = document.getElementById('gps-debug-panel');

    const endModal = document.getElementById('end-trip-modal');
    const btnCloseEndModal = document.getElementById('btn-close-end-modal');
    const btnCancelEnd = document.getElementById('btn-cancel-end');
    const btnConfirmEnd = document.getElementById('btn-confirm-end');

    let driverMap = null;
    let driverMarker = null;
    let watchId = null;
    let lastGpsTimestamp = null;
    let isFirstFix = true;
    let signalCheckInterval = null;

    // --- CHECK PERMISSIONS API ON LOAD ---
    if (navigator.permissions && navigator.permissions.query) {
        navigator.permissions.query({ name: 'geolocation' }).then((result) => {
            updatePermissionStatusUI(result.state);
            result.onchange = () => updatePermissionStatusUI(result.state);
        }).catch(err => console.log("Permissions API query fallback", err));
    }

    function updatePermissionStatusUI(state) {
        if (!gpsStatusText) return;
        if (state === 'granted') {
            gpsStatusText.textContent = "🟢 GPS Permission Granted";
            gpsStatusText.style.color = "#10b981";
        } else if (state === 'denied') {
            gpsStatusText.textContent = "🔴 GPS Permission Denied";
            gpsStatusText.style.color = "#ef4444";
        } else {
            gpsStatusText.textContent = "🟡 GPS Permission Required";
            gpsStatusText.style.color = "#f59e0b";
        }
    }

    // --- COLLAPSIBLE DEBUG PANEL TOGGLE ---
    if (btnToggleDebug && gpsDebugPanel) {
        btnToggleDebug.addEventListener('click', () => {
            gpsDebugPanel.classList.toggle('d-none');
        });
    }

    // --- STAGE 1: START JOURNEY (getCurrentPosition FIRST) ---
    if (btnStart) {
        btnStart.addEventListener('click', () => {
            if (!('geolocation' in navigator)) {
                alert("⚠️ Browser Geolocation is not supported on this device/browser.");
                return;
            }

            btnStart.disabled = true;
            btnStart.textContent = "📍 Requesting Fresh GPS Fix...";
            if (gpsPermissionAlert) gpsPermissionAlert.classList.remove('d-none');
            if (gpsStatusText) {
                gpsStatusText.textContent = "🟡 Obtaining fresh GPS position...";
                gpsStatusText.style.color = "#f59e0b";
            }

            const initialOptions = {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 0 // Force fresh position
            };

            navigator.geolocation.getCurrentPosition(
                async (pos) => {
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    const accuracy = pos.coords.accuracy;

                    console.log("GPS SUCCESS — First Fix Obtained:", {
                        latitude: lat,
                        longitude: lon,
                        accuracy: accuracy
                    });

                    if (gpsStatusText) {
                        gpsStatusText.textContent = `🟢 GPS Active (Accuracy: ${Math.round(accuracy)} m)`;
                        gpsStatusText.style.color = "#10b981";
                    }

                    // Send initial position & create Trip in Django
                    try {
                        const res = await fetch('/api/start-journey/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': getCsrfToken()
                            },
                            body: JSON.stringify({
                                latitude: lat,
                                longitude: lon,
                                accuracy: accuracy
                            })
                        });

                        if (!res.ok) {
                            const errText = await res.text();
                            console.error("Server start-journey error:", res.status, errText);
                            alert(`Server error (${res.status}): ${errText || 'Unable to start journey'}`);
                            btnStart.disabled = false;
                            btnStart.textContent = "🟢 START JOURNEY";
                            return;
                        }

                        const data = await res.json();

                        if (data.success) {
                            window.location.reload();
                        } else {
                            alert(data.error || "Failed to start journey.");
                            btnStart.disabled = false;
                            btnStart.textContent = "🟢 START JOURNEY";
                        }
                    } catch (err) {
                        console.error("GPS ERROR — Server start-journey failed:", err);
                        alert("Network error communicating with server: " + err.message);
                        btnStart.disabled = false;
                        btnStart.textContent = "🟢 START JOURNEY";
                    }
                },
                (err) => {
                    console.error("GPS ERROR — getCurrentPosition failed:", err);
                    btnStart.disabled = false;
                    btnStart.textContent = "🟢 START JOURNEY";

                    let errorMsg = "⚠️ Location request failed.";
                    if (err.code === err.PERMISSION_DENIED) {
                        errorMsg = "🔴 GPS permission denied. Please allow location access for Namma Sarthi in your browser.";
                        if (gpsStatusText) {
                            gpsStatusText.textContent = "🔴 LOCATION DENIED";
                            gpsStatusText.style.color = "#ef4444";
                        }
                    } else if (err.code === err.POSITION_UNAVAILABLE) {
                        errorMsg = "⚠️ GPS location is currently unavailable. Please check your device location settings.";
                        if (gpsStatusText) {
                            gpsStatusText.textContent = "🔴 GPS UNAVAILABLE";
                            gpsStatusText.style.color = "#ef4444";
                        }
                    } else if (err.code === err.TIMEOUT) {
                        errorMsg = "⚠️ GPS request timed out. Please check signal and try again.";
                        if (gpsStatusText) {
                            gpsStatusText.textContent = "🟠 GPS TIMEOUT";
                            gpsStatusText.style.color = "#f59e0b";
                        }
                    }

                    alert(errorMsg);
                },
                initialOptions
            );
        });
    }

    // --- STAGE 2: ACTIVE TRIP MANAGEMENT & CONTINUOUS watchPosition ---
    if (activeTripSection) {
        const tripId = activeTripSection.dataset.tripId;

        // Initialize Driver Leaflet Map
        const mapElem = document.getElementById('driver-map');
        if (mapElem) {
            driverMap = L.map('driver-map').setView([12.9779, 77.5724], 10);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap contributors'
            }).addTo(driverMap);

            setTimeout(() => {
                driverMap.invalidateSize();
            }, 300);
        }

        // Fetch initial route stops and bus info
        async function loadDriverTripStatus() {
            try {
                const res = await fetch(`/api/bus-location/${tripId}/`);
                const data = await res.json();

                document.getElementById('driver-current-stop').textContent = data.current_stop_name || 'En route';
                document.getElementById('driver-next-stop').textContent = data.next_stop_name || 'Destination';
                document.getElementById('driver-last-updated').textContent = data.last_updated || 'Just now';

                const routeStops = data.stops || [];
                if (driverMap && routeStops.length > 0) {
                    const latLons = routeStops.filter(s => s.latitude && s.longitude).map(s => [s.latitude, s.longitude]);
                    if (latLons.length > 0) {
                        L.polyline(latLons, { color: '#0284c7', weight: 4, opacity: 0.8 }).addTo(driverMap);

                        routeStops.forEach(s => {
                            if (s.latitude && s.longitude) {
                                L.circleMarker([s.latitude, s.longitude], {
                                    radius: 5,
                                    fillColor: '#059669',
                                    color: '#ffffff',
                                    weight: 2,
                                    fillOpacity: 0.9
                                }).bindPopup(`<b>${s.stop_village_name}</b><br>Stop #${s.stop_seq}`).addTo(driverMap);
                            }
                        });
                    }
                }

                if (data.latitude && data.longitude && driverMap) {
                    updateDriverMarker(data.latitude, data.longitude, data.bus_number);
                }
            } catch (err) {
                console.error("GPS ERROR — Loading trip status failed:", err);
            }
        }

        function updateDriverMarker(lat, lon, busNum) {
            if (!driverMap) return;

            const busIcon = L.divIcon({
                html: `<div style="font-size: 30px; filter: drop-shadow(0px 2px 5px rgba(0,0,0,0.5)); text-align: center;">🚌</div>`,
                className: 'custom-driver-bus-icon',
                iconSize: [36, 36],
                iconAnchor: [18, 18]
            });

            if (!driverMarker) {
                driverMarker = L.marker([lat, lon], { icon: busIcon }).addTo(driverMap);
                driverMarker.bindPopup(`<b>Bus ${busNum}</b><br>Real GPS Active`).openPopup();
                driverMap.setView([lat, lon], 16);
            } else {
                driverMarker.setLatLng([lat, lon]);
                if (isFirstFix) {
                    driverMap.setView([lat, lon], 16);
                    isFirstFix = false;
                }
            }
        }

        loadDriverTripStatus();

        // START CONTINUOUS watchPosition
        if ('geolocation' in navigator) {
            const watchOptions = {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 5000
            };

            let lastServerSyncTime = 0;

            watchId = navigator.geolocation.watchPosition(
                async (pos) => {
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    const accuracy = pos.coords.accuracy;
                    lastGpsTimestamp = Date.now();

                    console.log("GPS WATCH UPDATE:", {
                        latitude: lat,
                        longitude: lon,
                        accuracy: accuracy,
                        timestamp: new Date().toLocaleTimeString()
                    });

                    // Update UI Debugger & Badges
                    updateDebugPanel(lat, lon, accuracy);
                    updateGpsSignalUI(true, accuracy);

                    if (driverMap) {
                        updateDriverMarker(lat, lon, 'Your Bus');
                    }

                    // Throttle server updates to once every 5 seconds
                    const now = Date.now();
                    if (now - lastServerSyncTime >= 5000) {
                        lastServerSyncTime = now;

                        try {
                            const res = await fetch('/api/update-location/', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': getCsrfToken()
                                },
                                body: JSON.stringify({
                                    trip_id: tripId,
                                    latitude: lat,
                                    longitude: lon,
                                    accuracy: accuracy
                                })
                            });
                            const data = await res.json();

                            if (data.success) {
                                document.getElementById('debug-sync').textContent = "SUCCESS (" + new Date().toLocaleTimeString() + ")";
                                document.getElementById('debug-sync').style.color = "#4ade80";

                                if (data.is_stopped_long && stoppageAlertCard) {
                                    stoppageAlertCard.classList.remove('d-none');
                                }
                            }
                        } catch (e) {
                            console.error("GPS ERROR — Server update-location failed:", e);
                            document.getElementById('debug-sync').textContent = "FAILED";
                            document.getElementById('debug-sync').style.color = "#f87171";
                        }
                    }
                },
                (err) => {
                    console.error("GPS WATCH ERROR:", err);
                    updateGpsSignalUI(false, null, err.message);
                },
                watchOptions
            );

            // Signal Freshness Monitor (every 5s)
            signalCheckInterval = setInterval(() => {
                if (!lastGpsTimestamp) return;
                const elapsed = (Date.now() - lastGpsTimestamp) / 1000;
                const signalBadge = document.getElementById('driver-gps-signal-badge');
                if (!signalBadge) return;

                if (elapsed > 120) {
                    signalBadge.textContent = "🔴 LOCATION OFFLINE";
                    signalBadge.className = "badge badge-status-offline";
                } else if (elapsed > 30) {
                    signalBadge.textContent = "🟠 GPS SIGNAL DELAYED";
                    signalBadge.className = "badge badge-status-delayed";
                } else {
                    signalBadge.textContent = "🟢 GPS ACTIVE";
                    signalBadge.className = "badge badge-real";
                }
            }, 5000);
        }

        function updateDebugPanel(lat, lon, accuracy) {
            const elLat = document.getElementById('debug-lat');
            const elLon = document.getElementById('debug-lon');
            const elAcc = document.getElementById('debug-accuracy');
            const elTime = document.getElementById('debug-time');
            const elStatus = document.getElementById('debug-gps-status');
            const elAccuracyDisplay = document.getElementById('driver-gps-accuracy');

            if (elLat) elLat.textContent = lat.toFixed(5);
            if (elLon) elLon.textContent = lon.toFixed(5);
            if (elAcc) elAcc.textContent = Math.round(accuracy);
            if (elTime) elTime.textContent = new Date().toLocaleTimeString();
            if (elStatus) elStatus.textContent = "ACTIVE";
            if (elAccuracyDisplay) elAccuracyDisplay.textContent = Math.round(accuracy) + " m";
        }

        function updateGpsSignalUI(isActive, accuracy, errorMsg) {
            const badge = document.getElementById('driver-gps-signal-badge');
            if (!badge) return;

            if (isActive) {
                badge.textContent = `🟢 GPS ACTIVE (${Math.round(accuracy || 0)}m)`;
                badge.className = "badge badge-real";
            } else {
                badge.textContent = `🔴 GPS ERROR: ${errorMsg || 'No Signal'}`;
                badge.className = "badge badge-status-offline";
            }
        }

        // --- END JOURNEY HANDLERS (clearWatch) ---
        if (btnEnd) {
            btnEnd.addEventListener('click', () => {
                if (endModal) endModal.classList.remove('d-none');
            });
        }

        if (btnCloseEndModal) {
            btnCloseEndModal.addEventListener('click', () => {
                if (endModal) endModal.classList.add('d-none');
            });
        }

        if (btnCancelEnd) {
            btnCancelEnd.addEventListener('click', () => {
                if (endModal) endModal.classList.add('d-none');
            });
        }

        if (btnConfirmEnd) {
            btnConfirmEnd.addEventListener('click', async () => {
                // STOP GPS WATCHING
                if (watchId !== null) {
                    console.log("GPS WATCH STOPPED — clearWatch ID:", watchId);
                    navigator.geolocation.clearWatch(watchId);
                    watchId = null;
                }
                if (signalCheckInterval) clearInterval(signalCheckInterval);

                const formData = new FormData();
                formData.append('trip_id', tripId);

                try {
                    const res = await fetch('/api/end-journey/', {
                        method: 'POST',
                        headers: { 'X-CSRFToken': getCsrfToken() },
                        body: formData
                    });
                    const data = await res.json();
                    if (data.success) {
                        window.location.reload();
                    } else {
                        alert(data.error || "Failed to end journey.");
                    }
                } catch (e) {
                    console.error("End journey request failed", e);
                }
            });
        }

        // RESUME JOURNEY
        if (btnResume) {
            btnResume.addEventListener('click', async () => {
                const formData = new FormData();
                formData.append('trip_id', tripId);

                const res = await fetch('/api/resume-journey/', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCsrfToken() },
                    body: formData
                });
                const data = await res.json();
                if (data.success) {
                    if (stoppageAlertCard) stoppageAlertCard.classList.add('d-none');
                    btnResume.classList.add('d-none');
                    const banner = document.getElementById('delay-status-banner');
                    if (banner) banner.classList.add('d-none');
                    const statusBadge = document.getElementById('driver-status-badge');
                    if (statusBadge) {
                        statusBadge.textContent = '🟢 LIVE';
                        statusBadge.className = 'badge badge-status-live';
                    }
                }
            });
        }

        // STOPPAGE REASON BUTTONS
        const reasonBtns = document.querySelectorAll('.btn-reason');
        reasonBtns.forEach(btn => {
            btn.addEventListener('click', async () => {
                const reason = btn.dataset.reason;
                const formData = new FormData();
                formData.append('trip_id', tripId);
                formData.append('reason', reason);

                const res = await fetch('/api/report-stop-reason/', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCsrfToken() },
                    body: formData
                });
                const data = await res.json();

                if (data.success) {
                    if (stoppageAlertCard) stoppageAlertCard.classList.add('d-none');
                    const banner = document.getElementById('delay-status-banner');
                    const reasonText = document.getElementById('current-reason-text');
                    if (banner && reasonText) {
                        reasonText.textContent = reason;
                        banner.classList.remove('d-none');
                    }
                    if (btnResume) btnResume.classList.remove('d-none');
                }
            });
        });
    }
}

/* ==========================================================================
   2. PASSENGER DASHBOARD & LIVE MAP MODAL POLLING
   ========================================================================== */
function initPassengerDashboard() {
    const searchForm = document.getElementById('bus-search-form');
    const sourceSelect = document.getElementById('source_stop');
    const destSelect = document.getElementById('destination_stop');
    const resultsLoading = document.getElementById('results-loading');
    const noBusesAlert = document.getElementById('no-buses-alert');
    const busCardsContainer = document.getElementById('bus-cards-container');

    const modal = document.getElementById('map-modal');
    const btnCloseModal = document.getElementById('btn-close-modal');

    let passengerMap = null;
    let passengerBusMarker = null;
    let activeMapPollInterval = null;

    // --- CASCADING DESTINATION DROPDOWN LOGIC ---
    if (sourceSelect && destSelect) {
        sourceSelect.addEventListener('change', async (e) => {
            const selectedSource = e.target.value;

            destSelect.innerHTML = '';
            destSelect.disabled = true;

            if (!selectedSource) {
                destSelect.innerHTML = '<option value="">-- Select Source First --</option>';
                return;
            }

            destSelect.innerHTML = '<option value="">Loading valid destinations...</option>';

            try {
                const res = await fetch(`/api/valid-destinations/?source=${encodeURIComponent(selectedSource)}`);
                const data = await res.json();
                const destinations = data.destinations || [];

                destSelect.innerHTML = '';

                if (destinations.length === 0) {
                    destSelect.innerHTML = '<option value="">No destinations available from this station</option>';
                    destSelect.disabled = true;
                } else {
                    destSelect.innerHTML = '<option value="">-- Select Destination ▼ --</option>';
                    destinations.forEach(dest => {
                        const opt = document.createElement('option');
                        opt.value = dest;
                        opt.textContent = dest;
                        destSelect.appendChild(opt);
                    });
                    destSelect.disabled = false;
                }
            } catch (err) {
                console.error("Error fetching valid destinations", err);
                destSelect.innerHTML = '<option value="">Error loading destinations</option>';
                destSelect.disabled = true;
            }
        });
    }

    if (searchForm) {
        searchForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const source = document.getElementById('source_stop').value;
            const destination = document.getElementById('destination_stop').value;

            if (!source || !destination) {
                alert("Please select source and destination stops.");
                return;
            }

            if (source === destination) {
                alert("Source and Destination stops cannot be identical.");
                return;
            }

            resultsLoading.classList.remove('d-none');
            noBusesAlert.classList.add('d-none');
            busCardsContainer.innerHTML = '';

            try {
                const res = await fetch(`/api/search-buses/?source=${encodeURIComponent(source)}&destination=${encodeURIComponent(destination)}`);
                const data = await res.json();

                resultsLoading.classList.add('d-none');

                if (!data.buses || data.buses.length === 0) {
                    noBusesAlert.classList.remove('d-none');
                    return;
                }

                data.buses.forEach(b => {
                    const card = createBusCard(b);
                    busCardsContainer.appendChild(card);
                });
            } catch (err) {
                console.error("Error searching buses", err);
                resultsLoading.classList.add('d-none');
                alert("Failed to search buses.");
            }
        });
    }

    function createBusCard(bus) {
        const div = document.createElement('div');
        div.className = 'bus-card';

        let statusBadge = '<span class="badge badge-status-live">🟢 LIVE</span>';
        if (bus.status === 'DELAYED' || bus.status === 'STOPPED') {
            statusBadge = `<span class="badge badge-status-delayed">🟠 ${bus.status}</span>`;
        }

        const delayNotice = bus.stop_reason ? `
            <div class="alert alert-warning" style="margin-top: 0.75rem; padding: 0.75rem; font-size: 0.85rem;">
                <strong>⚠️ BUS DELAYED</strong><br>Reason: ${bus.stop_reason}
            </div>
        ` : '';

        const hasSourceEta = (bus.eta_source_min !== null && bus.eta_source_min !== undefined && !isNaN(bus.eta_source_min));
        const hasDestEta = (bus.eta_dest_min !== null && bus.eta_dest_min !== undefined && !isNaN(bus.eta_dest_min));

        // 1. YOUR STOP CALCULATIONS
        let sourceMainText = "Arrival time unavailable";
        let sourceSubtext = "ETA unavailable";
        if (hasSourceEta) {
            const sourceEta = parseInt(bus.eta_source_min, 10);
            if (sourceEta <= 0) {
                sourceMainText = "Bus has reached your stop";
                sourceSubtext = "Arriving now";
            } else {
                const clockTime = calculateArrivalTime(sourceEta);
                sourceMainText = clockTime ? `ARRIVING AT ${clockTime}` : "Arrival time unavailable";
                sourceSubtext = `${sourceEta} min from now`;
            }
        }

        // 2. YOUR JOURNEY CALCULATIONS (destination_eta - your_stop_eta)
        let journeyMainText = "Journey duration unavailable";
        let journeySubtext = "";
        if (hasSourceEta && hasDestEta) {
            const sourceEta = parseInt(bus.eta_source_min, 10);
            const destEta = parseInt(bus.eta_dest_min, 10);
            const journeyMin = destEta - sourceEta;

            if (journeyMin < 0) {
                journeyMainText = "Journey duration unavailable";
                journeySubtext = "";
            } else if (journeyMin === 0) {
                journeyMainText = "0 min";
                journeySubtext = "from your stop to destination";
            } else {
                journeyMainText = `${journeyMin} min`;
                journeySubtext = "from your stop to destination";
            }
        }

        // 3. DESTINATION CALCULATIONS
        let destMainText = "Arrival time unavailable";
        let destSubtext = "ETA unavailable";
        if (hasDestEta) {
            const destEta = parseInt(bus.eta_dest_min, 10);
            if (destEta <= 0) {
                destMainText = "Bus has reached destination";
                destSubtext = "Reached destination";
            } else {
                const clockTime = calculateArrivalTime(destEta);
                destMainText = clockTime ? `REACHING AT ${clockTime}` : "Arrival time unavailable";
                destSubtext = `${destEta} min from now`;
            }
        }

        div.innerHTML = `
            <div class="bus-card-header">
                <div>
                    <span class="badge-bus">🚌 ${bus.bus_number}</span>
                    <h3>${bus.route_name}</h3>
                    <p class="bus-route-name">Service: <strong>${bus.service_type}</strong></p>
                </div>
                <div>${statusBadge}</div>
            </div>

            <div style="font-size: 0.9rem; margin-bottom: 0.5rem;">
                <p><strong>Current Stop:</strong> Near ${bus.current_stop_name}</p>
                <p><strong>Next Stop:</strong> ${bus.next_stop_name}</p>
                <p><strong>Distance to Your Stop:</strong> ${bus.dist_to_source_km} km</p>
            </div>

            <div class="eta-timeline">
                <div class="timeline-box timeline-box-stop">
                    <div class="timeline-label">📍 YOUR STOP</div>
                    <div class="timeline-main-time">${sourceMainText}</div>
                    <div class="timeline-subtext">${sourceSubtext}</div>
                </div>

                <div class="timeline-arrow">↓</div>

                <div class="timeline-box timeline-box-journey">
                    <div class="timeline-label">🚌 YOUR JOURNEY</div>
                    <div class="timeline-main-time">${journeyMainText}</div>
                    ${journeySubtext ? `<div class="timeline-subtext">${journeySubtext}</div>` : ''}
                </div>

                <div class="timeline-arrow">↓</div>

                <div class="timeline-box timeline-box-dest">
                    <div class="timeline-label">🏁 DESTINATION</div>
                    <div class="timeline-main-time">${destMainText}</div>
                    <div class="timeline-subtext">${destSubtext}</div>
                </div>
            </div>

            ${delayNotice}

            <button type="button" class="btn btn-primary btn-block btn-view-map" data-trip-id="${bus.trip_id}" data-bus-num="${bus.bus_number}" data-route="${bus.route_name}">
                🗺️ VIEW LIVE MAP
            </button>
        `;

        const btnMap = div.querySelector('.btn-view-map');
        btnMap.addEventListener('click', () => {
            openPassengerMapModal(bus.trip_id, bus.bus_number, bus.route_name);
        });

        return div;
    }

    function openPassengerMapModal(tripId, busNum, routeName) {
        document.getElementById('modal-bus-title').textContent = `🚌 Bus ${busNum} — ${routeName}`;
        modal.classList.remove('d-none');

        if (!passengerMap) {
            passengerMap = L.map('passenger-map').setView([12.9779, 77.5724], 10);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap contributors'
            }).addTo(passengerMap);
        }

        setTimeout(() => {
            if (passengerMap) passengerMap.invalidateSize();
        }, 300);

        fetchAndRenderPassengerMap(tripId);

        if (activeMapPollInterval) clearInterval(activeMapPollInterval);
        activeMapPollInterval = setInterval(() => {
            fetchAndRenderPassengerMap(tripId);
        }, 5000);
    }

    async function fetchAndRenderPassengerMap(tripId) {
        try {
            const res = await fetch(`/api/bus-location/${tripId}/`);
            const data = await res.json();

            const modalDelayNotice = document.getElementById('modal-delay-notice');
            const modalDelayReason = document.getElementById('modal-delay-reason');

            if (data.stop_reason) {
                modalDelayReason.textContent = data.stop_reason;
                modalDelayNotice.classList.remove('d-none');
            } else {
                modalDelayNotice.classList.add('d-none');
            }

            const stops = data.stops || [];
            if (stops.length > 0) {
                const latLons = stops.filter(s => s.latitude && s.longitude).map(s => [s.latitude, s.longitude]);
                if (latLons.length > 0) {
                    L.polyline(latLons, { color: '#059669', weight: 5, opacity: 0.85 }).addTo(passengerMap);

                    stops.forEach(s => {
                        if (s.latitude && s.longitude) {
                            L.circleMarker([s.latitude, s.longitude], {
                                radius: 5,
                                fillColor: '#0284c7',
                                color: '#ffffff',
                                weight: 2,
                                fillOpacity: 0.9
                            }).bindPopup(`<b>${s.stop_village_name}</b><br>Stop #${s.stop_seq}`).addTo(passengerMap);
                        }
                    });
                }
            }

            if (data.latitude && data.longitude) {
                const busIcon = L.divIcon({
                    html: `<div style="font-size: 32px; filter: drop-shadow(0px 2px 5px rgba(0,0,0,0.5)); text-align: center;">🚌</div>`,
                    className: 'passenger-bus-icon',
                    iconSize: [40, 40],
                    iconAnchor: [20, 20]
                });

                if (!passengerBusMarker) {
                    passengerBusMarker = L.marker([data.latitude, data.longitude], { icon: busIcon }).addTo(passengerMap);
                    passengerMap.setView([data.latitude, data.longitude], 15);
                } else {
                    passengerBusMarker.setLatLng([data.latitude, data.longitude]);
                }
                passengerBusMarker.bindPopup(`<b>Bus ${data.bus_number}</b><br>Status: ${data.status}<br>Updated: ${data.last_updated}`).openPopup();
            }
        } catch (err) {
            console.error("Failed updating passenger map", err);
        }
    }

    if (btnCloseModal) {
        btnCloseModal.addEventListener('click', () => {
            modal.classList.add('d-none');
            if (activeMapPollInterval) {
                clearInterval(activeMapPollInterval);
                activeMapPollInterval = null;
            }
        });
    }
}
