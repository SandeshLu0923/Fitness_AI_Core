import { useState, useEffect } from 'react';
import axios from 'axios';
import { Locate, MapPin, Star, Navigation, Search } from 'lucide-react';

interface GymFacility {
  name: string;
  locality: string;
  address: string;
  rating: number;
  distance_km: number;
}

interface GymTabProps {
  userId?: string;
  nearbyRequestToken?: number;
}

const DEFAULT_RADIUS_KM = 10;

const CITY_COORDINATES: Record<string, { latitude: number; longitude: number; name: string }> = {
  bangalore: { latitude: 12.9716, longitude: 77.5946, name: 'Bangalore' },
  bengaluru: { latitude: 12.9716, longitude: 77.5946, name: 'Bangalore' },
  mumbai: { latitude: 19.076, longitude: 72.8777, name: 'Mumbai' },
  delhi: { latitude: 28.7041, longitude: 77.1025, name: 'Delhi' },
  hyderabad: { latitude: 17.385, longitude: 78.4867, name: 'Hyderabad' },
  pune: { latitude: 18.5204, longitude: 73.8567, name: 'Pune' },
  chennai: { latitude: 13.0827, longitude: 80.2707, name: 'Chennai' },
  kolkata: { latitude: 22.5726, longitude: 88.3639, name: 'Kolkata' },
  ahmedabad: { latitude: 23.0225, longitude: 72.5714, name: 'Ahmedabad' },
  jaipur: { latitude: 26.9124, longitude: 75.7873, name: 'Jaipur' },
  lucknow: { latitude: 26.8467, longitude: 80.9462, name: 'Lucknow' },
  surat: { latitude: 21.1458, longitude: 72.1588, name: 'Surat' },
  chandigarh: { latitude: 30.7333, longitude: 76.7794, name: 'Chandigarh' },
  indore: { latitude: 22.7196, longitude: 75.8577, name: 'Indore' },
};

const DEFAULT_LOCATION = {
  latitude: 13.0827,
  longitude: 80.2707,
  label: 'Chennai',
};

export default function GymTab({ userId = 'runner_jack', nearbyRequestToken = 0 }: GymTabProps) {
  const [citySearch, setCitySearch] = useState('');
  const [userLocation, setUserLocation] = useState({
    latitude: DEFAULT_LOCATION.latitude,
    longitude: DEFAULT_LOCATION.longitude,
  });
  const [gyms, setGyms] = useState<GymFacility[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [resultLabel, setResultLabel] = useState('Your location');
  const [locationReady, setLocationReady] = useState(false);
  const [isCityFiltered, setIsCityFiltered] = useState(false);

  const fetchBrowserLocation = () =>
    new Promise<{ latitude: number; longitude: number }>((resolve, reject) => {
      if (!('geolocation' in navigator)) {
        reject(new Error('Geolocation is not supported.'));
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (position) => {
          const { latitude, longitude } = position.coords;
          resolve({ latitude, longitude });
        },
        (error) => reject(error)
      );
    });

  const fetchGymsForCoordinates = async (
    latitude: number,
    longitude: number,
    label: string,
    cityFiltered: boolean
  ) => {
    const response = await axios.post('http://localhost:8000/api/recommender/explore-gyms', {
      latitude,
      longitude,
      search_radius_km: DEFAULT_RADIUS_KM,
    });

    const foundGyms = response.data.recommended_gyms || [];
    setGyms(foundGyms);
    setResultLabel(label);
    setIsCityFiltered(cityFiltered);

    if (foundGyms.length === 0) {
      setErrorMsg(`No fitness facilities found within ${DEFAULT_RADIUS_KM}km of ${label}.`);
      return;
    }

    setErrorMsg('');
  };

  const resolveUserLocation = async () => {
    try {
      const response = await axios.get(`http://localhost:8000/api/profile/${userId}`);
      const latitude = Number(response.data.latitude);
      const longitude = Number(response.data.longitude);

      if (latitude && longitude) {
        return { latitude, longitude, label: 'Your location' };
      }

      throw new Error('Profile location is empty.');
    } catch {
      const browserLocation = await fetchBrowserLocation();
      return { ...browserLocation, label: 'Your location' };
    }
  };

  const resolveLiveUserLocation = async () => {
    try {
      const browserLocation = await fetchBrowserLocation();
      return { ...browserLocation, label: 'Your location' };
    } catch {
      return resolveUserLocation();
    }
  };

  useEffect(() => {
    const fetchUserLocation = async () => {
      try {
        const location = await resolveUserLocation();
        setUserLocation({ latitude: location.latitude, longitude: location.longitude });
        setResultLabel(location.label);
        setErrorMsg('');
      } catch {
        setUserLocation({
          latitude: DEFAULT_LOCATION.latitude,
          longitude: DEFAULT_LOCATION.longitude,
        });
        setResultLabel(DEFAULT_LOCATION.label);
        setErrorMsg('Could not access your saved or browser location. Showing gyms near Chennai.');
      } finally {
        setLocationReady(true);
      }
    };
    fetchUserLocation();
  }, [userId]);

  useEffect(() => {
    if (!locationReady || isCityFiltered) return;

    const debounceTimer = setTimeout(async () => {
      setLoading(true);
      try {
        await fetchGymsForCoordinates(userLocation.latitude, userLocation.longitude, resultLabel || 'Your location', false);
      } catch {
        setErrorMsg('Could not load gyms near your location. Try searching by city.');
      } finally {
        setLoading(false);
      }
    }, 500);

    return () => clearTimeout(debounceTimer);
  }, [userLocation, locationReady, isCityFiltered]);

  useEffect(() => {
    if (!nearbyRequestToken) return;
    handleNearbySearch();
  }, [nearbyRequestToken]);

  const handleCitySearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!citySearch.trim()) {
      setErrorMsg('Please enter a city name');
      return;
    }

    const cityKey = citySearch.toLowerCase().trim();
    const cityCoords = CITY_COORDINATES[cityKey];
    if (!cityCoords) {
      setErrorMsg(`City "${citySearch}" not found. Try: Bangalore, Mumbai, Delhi, Hyderabad, Pune, Chennai, Kolkata`);
      return;
    }

    setLoading(true);
    setErrorMsg('');

    try {
      await fetchGymsForCoordinates(cityCoords.latitude, cityCoords.longitude, cityCoords.name, true);
    } catch {
      setErrorMsg('Failed to search gyms. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleNearbySearch = async () => {
    setLoading(true);
    setErrorMsg('');
    setCitySearch('');

    try {
      const location = await resolveLiveUserLocation();
      const coordinates = { latitude: location.latitude, longitude: location.longitude };
      setUserLocation(coordinates);
      await fetchGymsForCoordinates(coordinates.latitude, coordinates.longitude, location.label, false);
    } catch {
      setErrorMsg('Could not fetch your location. Please enable location access or complete your profile location.');
    } finally {
      setLoading(false);
      setLocationReady(true);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <section className="w-full bg-[#1e1e1e] border-2 border-cyan-500/60 rounded-xl p-6 shadow-xl hover:border-cyan-400/80 transition-all">
        <h3 className="text-sm font-black uppercase tracking-widest text-cyan-400 mb-4">Search by City</h3>
        <form onSubmit={handleCitySearch} className="space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">City Name</label>
            <input
              type="text"
              value={citySearch}
              onChange={(e) => setCitySearch(e.target.value)}
              placeholder="e.g., Delhi..."
              className="w-full bg-[#121212] border border-gray-800 rounded-lg px-4 py-2.5 text-gray-200 focus:outline-none focus:border-cyan-500 text-sm transition-colors"
              required
            />
            <p className="text-[10px] text-gray-600 mt-1">
              Supported: Bangalore, Mumbai, Delhi, Hyderabad, Pune, Chennai, Kolkata, Ahmedabad, Jaipur, Lucknow, Surat, Chandigarh, Indore
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-cyan-600 hover:bg-cyan-700 disabled:bg-gray-700 text-white font-bold py-2.5 rounded-lg transition-colors flex items-center justify-center space-x-2 shadow-md text-sm"
            >
              <Search size={16} />
              <span>{loading ? 'Searching...' : 'Search Gyms'}</span>
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={handleNearbySearch}
              className="w-full bg-[#121212] hover:bg-cyan-500/10 disabled:bg-gray-700 text-cyan-400 border border-cyan-500/40 font-bold py-2.5 rounded-lg transition-colors flex items-center justify-center space-x-2 shadow-md text-sm"
            >
              <Locate size={16} />
              <span>Nearby Gyms</span>
            </button>
          </div>

          {resultLabel && (
            <p className="text-xs text-cyan-400 text-center border-t border-gray-800 pt-3 mt-3">
              Showing: <span className="font-bold">{resultLabel}</span>
            </p>
          )}
        </form>
      </section>

      <section>
        {errorMsg && (
          <div className="p-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm rounded-lg mb-4">
            {errorMsg}
          </div>
        )}

        {loading && (
          <div className="text-center py-12 text-gray-500">
            <p className="text-sm">Loading gyms...</p>
          </div>
        )}

        {!loading && gyms.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <p className="text-sm">
              {isCityFiltered
                ? 'No gyms found. Try a different city or increase the search radius.'
                : 'No gyms found near your location. Try searching by city.'}
            </p>
          </div>
        )}

        {!loading && gyms.length > 0 && (
          <>
            <h3 className="text-sm font-black uppercase tracking-widest text-cyan-400 mb-4">
              {isCityFiltered ? `Results for ${resultLabel}` : 'Gyms Near Your Location'}
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {gyms.map((gym, idx) => (
                <div
                  key={`${gym.name}-${idx}`}
                  className="bg-[#1e1e1e] border-2 border-cyan-500/60 rounded-lg p-5 flex flex-col justify-between hover:border-cyan-400/80 hover:bg-cyan-500/5 transition-all duration-150 shadow-lg cursor-pointer group"
                >
                  <div>
                    <div className="flex items-start justify-between mb-3">
                      <h4 className="text-base font-bold text-gray-100 group-hover:text-cyan-400 transition-colors">{gym.name}</h4>
                      <div className="flex items-center space-x-1 bg-yellow-500/10 text-yellow-400 text-xs px-2 py-1 rounded border border-yellow-500/20">
                        <Star size={12} className="fill-current" />
                        <span className="font-bold">{Number(gym.rating || 0).toFixed(1)}</span>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2 text-cyan-400 text-xs font-semibold mb-3 uppercase tracking-wider">
                      <Navigation size={12} />
                      <span>{gym.locality}</span>
                    </div>

                    <div className="flex items-start space-x-3 text-sm text-gray-400 mb-4 bg-[#121212] p-3 rounded border border-gray-900">
                      <MapPin size={14} className="text-gray-500 shrink-0 mt-0.5" />
                      <p className="leading-relaxed text-xs">{gym.address || 'Address not available'}</p>
                    </div>
                  </div>

                  <div className="pt-4 border-t border-gray-800 flex items-center justify-between text-xs text-gray-500">
                    <span>DISTANCE</span>
                    <span className="text-cyan-400 font-bold text-sm bg-cyan-500/10 px-2.5 py-1 rounded border border-cyan-500/20">
                      {gym.distance_km} km
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
