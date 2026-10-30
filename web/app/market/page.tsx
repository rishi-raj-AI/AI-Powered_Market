import './marketplace.css';
'use client';

import {Suspense, useEffect, useMemo, useRef, useState} from 'react';
import Link from 'next/link';
import {useRouter, useSearchParams} from 'next/navigation';
import {Clock3, MapPin, Search, ShoppingBag, Store as StoreIcon, Truck} from 'lucide-react';
import {DiscoveryProduct, gaonApi, NearbyStore, Store, Village} from '@/lib/api';
import {Nav} from '@/components/Nav';
import {UniversalLocationSearch} from '@/components/UniversalLocationSearch';

type MarketStore = Store | NearbyStore;

export default function Market() {
  return <Suspense fallback={<><Nav /><main className="container section"><div className="panel">Loading marketplace…</div></main></>}><MarketContent /></Suspense>;
}

function MarketContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const locationQuery = searchParams.toString();
  const [villages, setVillages] = useState<Village[]>([]);
  const [stores, setStores] = useState<MarketStore[]>([]);
  const [v, setV] = useState('');
  const [q, setQ] = useState('');
  const [delivery, setDelivery] = useState(false);
  const [products, setProducts] = useState<DiscoveryProduct[]>([]);
  const [matchedStoreIds, setMatchedStoreIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [msg, setMsg] = useState('');
  const [storesLoadError, setStoresLoadError] = useState('');
  const [searchError, setSearchError] = useState('');
  const [storesErrorContext, setStoresErrorContext] = useState<string | null>(null);
  const [searchErrorContext, setSearchErrorContext] = useState<string | null>(null);
  const [storesRefresh, setStoresRefresh] = useState(0);
  const [searchRefresh, setSearchRefresh] = useState(0);
  const [discoveryIntent, setDiscoveryIntent] = useState(0);
  const [loadedStoresContext, setLoadedStoresContext] = useState<string | null>(null);
  const [loadedDiscoveryContext, setLoadedDiscoveryContext] = useState<string | null>(null);
  const storesRequest = useRef(0);
  const discoveryRequest = useRef(0);

  const location = useMemo(() => {
    const params = new URLSearchParams(locationQuery);
    const nextLat = Number(params.get('lat'));
    const nextLng = Number(params.get('lng'));
    const nearby = params.has('lat') && params.has('lng') && Number.isFinite(nextLat) && Number.isFinite(nextLng);
    return {
      nearby,
      lat: nearby ? nextLat : undefined,
      lng: nearby ? nextLng : undefined,
      label: nearby ? params.get('location') || 'Selected location' : '',
      serviceable: nearby ? params.get('serviceable') === '1' ? true : params.get('serviceable') === '0' ? false : null : null,
      area: nearby ? params.get('service_area') || '' : '',
    };
  }, [locationQuery]);
  const listQuery = location.nearby ? '' : q;
  const storesContext = JSON.stringify({
    nearby: location.nearby,
    lat: location.lat ?? null,
    lng: location.lng ?? null,
    village: v,
    query: listQuery,
    delivery,
  });
  const discoveryQuery = q.trim();
  const discoveryActive = location.nearby && location.lat !== undefined && location.lng !== undefined && Boolean(discoveryQuery);
  const discoveryContext = JSON.stringify({
    nearby: location.nearby,
    lat: location.lat ?? null,
    lng: location.lng ?? null,
    query: discoveryQuery,
    delivery,
    intent: discoveryIntent,
    refresh: searchRefresh,
  });
  const hasLoadedStores = loadedStoresContext === storesContext;
  const hasSearched = discoveryActive && loadedDiscoveryContext === discoveryContext;
  const activeStoresError = storesErrorContext === storesContext ? storesLoadError : '';
  const activeSearchError = searchErrorContext === discoveryContext ? searchError : '';

  useEffect(() => {
    let active = true;
    gaonApi.villages()
      .then(data => {
        if (active) setVillages(data);
      })
      .catch((error: unknown) => {
        if (active) setMsg(error instanceof Error ? error.message : 'Service areas are temporarily unavailable.');
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const requestId = ++storesRequest.current;
    let active = true;
    setLoading(true);
    setStoresLoadError('');
    setStoresErrorContext(storesContext);
    setMsg('');
    const request = location.nearby && location.lat !== undefined && location.lng !== undefined
      ? gaonApi.nearbyStores(location.lat, location.lng, 20, delivery || undefined)
      : gaonApi.stores(v || undefined, listQuery || undefined, delivery || undefined);
    request
      .then(data => {
        if (!active || requestId !== storesRequest.current) return;
        setStores(data);
        setLoadedStoresContext(storesContext);
        if (location.nearby) setMsg(data.length ? `Showing places near ${location.label}.` : `No active stores found near ${location.label} yet.`);
      })
      .catch((error: unknown) => {
        if (!active || requestId !== storesRequest.current) return;
        setStoresLoadError(error instanceof Error ? error.message : 'Marketplace availability is temporarily unavailable.');
        setStoresErrorContext(storesContext);
      })
      .finally(() => {
        if (active && requestId === storesRequest.current) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [delivery, listQuery, location.label, location.lat, location.lng, location.nearby, storesContext, storesRefresh, v]);

  useEffect(() => {
    const requestId = ++discoveryRequest.current;
    if (!discoveryActive || location.lat === undefined || location.lng === undefined) {
      setProducts([]);
      setMatchedStoreIds([]);
      setSearching(false);
      setSearchError('');
      setSearchErrorContext(discoveryContext);
      return;
    }
    let active = true;
    setProducts([]);
    setMatchedStoreIds([]);
    setSearching(true);
    setSearchError('');
    setSearchErrorContext(discoveryContext);
    const timer = window.setTimeout(async () => {
      try {
        const result = await gaonApi.discovery(discoveryQuery, location.lat!, location.lng!, 20, delivery || undefined);
        if (!active || requestId !== discoveryRequest.current) return;
        setProducts(result.products);
        setMatchedStoreIds([...new Set([...result.stores.map(store => store.id), ...result.products.map(product => product.store_id)])]);
        setLoadedDiscoveryContext(discoveryContext);
      } catch (error: unknown) {
        if (!active || requestId !== discoveryRequest.current) return;
        setSearchError(error instanceof Error ? error.message : 'Nearby inventory is temporarily unavailable.');
        setSearchErrorContext(discoveryContext);
      } finally {
        if (active && requestId === discoveryRequest.current) setSearching(false);
      }
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [delivery, discoveryActive, discoveryContext, discoveryQuery, location.lat, location.lng, searchRefresh]);

  const shown = useMemo(() => {
    if (location.nearby) {
      if (!discoveryQuery) return stores;
      if (!hasSearched) return [];
      const matched = new Set(matchedStoreIds);
      return stores.filter(store => matched.has(store.id));
    }
    return stores.filter(store => !q || store.name.toLowerCase().includes(q.toLowerCase()) || (store.description || '').toLowerCase().includes(q.toLowerCase()));
  }, [discoveryQuery, hasSearched, location.nearby, matchedStoreIds, q, stores]);

  const resultsAreConfirmed = hasLoadedStores && (!discoveryActive || hasSearched);
  const noResults = resultsAreConfirmed && !loading && !searching && !activeStoresError && !activeSearchError && shown.length === 0 && (!discoveryActive || products.length === 0);

  function clearLocation() {
    storesRequest.current += 1;
    discoveryRequest.current += 1;
    setProducts([]);
    setMatchedStoreIds([]);
    setSearching(false);
    setMsg('');
    router.replace('/market');
  }

  return <><Nav /><main className="container section customerMarket" aria-busy={loading || searching}>
    <div className="sectionHead marketWelcome"><div><span className="eyebrow">DISCOVER YOUR NEIGHBOURHOOD</span><h2>Fresh finds, just around the corner.</h2><p className="muted">Discover trusted local shops, everyday essentials and nearby favourites. Choose a landmark or area to see live availability.</p></div><div className="marketWelcomeIcon" aria-hidden="true"><ShoppingBag size={54}/></div></div>
    {location.serviceable === false && <div className="notice"><strong>We’re not live at this exact point yet.</strong> {location.area && `Nearest active service area: ${location.area}. `}You can still browse nearby availability.</div>}
    {location.serviceable === true && location.area && <div className="notice">Serviceable through <strong>{location.area}</strong>.</div>}
    {msg && <div className="notice">{msg}</div>}
    <div className="panel" style={{marginBottom: 14}}><UniversalLocationSearch compact />{location.nearby && location.label && <div className="row muted" style={{marginTop: 10}}><MapPin size={15} /><strong>{location.label}</strong></div>}</div>
    <div className="panel filterBar marketFilters"><div className="search" style={{flex: 1, minWidth: 220}}><Search size={19} /><input aria-label="Search marketplace availability" value={q} onChange={event => { setQ(event.target.value); setDiscoveryIntent(current => current + 1); }} placeholder={location.nearby ? 'Search products, categories or stores nearby...' : 'Search stores or essentials...'} /></div><select aria-label="Service area" value={v} onChange={event => { setV(event.target.value); clearLocation(); }}><option value="">All service areas</option>{villages.map(village => <option value={village.id} key={village.id}>{village.name}, {village.district}</option>)}</select><label className="toggleRow"><input type="checkbox" checked={delivery} onChange={event => { setDelivery(event.target.checked); setDiscoveryIntent(current => current + 1); }} /><Truck size={16} /> Delivery only</label></div>
    {activeStoresError && <div className="notice" role="alert"><span>{hasLoadedStores ? 'Unable to refresh marketplace availability. Showing the last confirmed availability. ' : 'Unable to load marketplace availability. '}{activeStoresError}</span><button type="button" className="btn secondary" disabled={loading} onClick={() => setStoresRefresh(current => current + 1)}>Retry stores</button></div>}
    {discoveryActive && <section style={{marginTop: 18}}><strong role={searching || !hasSearched ? 'status' : undefined}>{searching || !hasSearched ? 'Searching nearby inventory…' : `${products.length} available product${products.length === 1 ? '' : 's'} matched`}</strong>{activeSearchError && <div className="notice" role="alert"><span>Unable to search nearby inventory. {activeSearchError}</span><button type="button" className="btn secondary" disabled={searching} onClick={() => setSearchRefresh(current => current + 1)}>Retry nearby search</button></div>}{hasSearched && products.length > 0 && <div className="grid storeGrid" style={{marginTop: 10}}>{products.slice(0, 12).map(product => <Link className="card marketProductCard" href={`/market/${product.store_id}`} key={product.listing_id}><div className="row space"><span className="storeIcon"><ShoppingBag size={20} /></span><span className="pill">{product.distance_km.toFixed(1)} km</span></div><h3>{product.name}</h3><p className="muted">{product.brand ? `${product.brand} • ` : ''}{product.unit}</p><strong>₹{product.price}</strong><div className="muted" style={{marginTop: 8}}>{product.store_name}</div></Link>)}</div>}</section>}
    <div className="row space" style={{margin: '18px 0'}}><strong>{loading || !hasLoadedStores ? 'Loading stores…' : `${shown.length} store${shown.length === 1 ? '' : 's'} found`}</strong><div className="row marketAvailabilityActions"><button type="button" className="btn secondary" disabled={loading} onClick={() => setStoresRefresh(current => current + 1)}>Refresh availability</button>{location.nearby && <button type="button" className="btn ghost" onClick={clearLocation}>Clear location filter</button>}</div></div>
    {loading && !hasLoadedStores && <p className="muted" role="status">Loading marketplace availability…</p>}
    {hasLoadedStores && <div className="grid storeGrid">{shown.map(store => { const distance = 'distance_km' in store ? store.distance_km : null; return <Link className="card storeCard marketStoreCard" href={`/market/${store.id}`} key={store.id}><div className="row space"><span className="storeIcon"><StoreIcon size={22} /></span><div className="row">{store.delivery_enabled && <span className="pill"><Truck size={13} /> Delivery</span>}{store.pickup_enabled && <span className="pill">Pickup</span>}</div></div><h3>{store.name}</h3><p className="muted clamp2">{store.description || 'Verified local store serving this area.'}</p><span className={`badge status-${store.is_open_now ? 'approved' : 'cancelled'}`}>{store.is_open_now ? 'Open now' : 'Closed now'}</span><div className="stack compact"><div className="row muted"><MapPin size={15} />{store.landmark || 'Local market'}{distance !== null && <strong> • {distance} km</strong>}</div>{(store.opens_at || store.closes_at) && <div className="row muted"><Clock3 size={15} />{store.opens_at?.slice(0, 5) || '—'} – {store.closes_at?.slice(0, 5) || '—'} IST</div>}</div><span className="cardLink">View store →</span></Link>; })}</div>}
    {noResults && <div className="panel emptyState"><StoreIcon size={34} /><h3>No live availability found here yet</h3><p className="muted">Try another area or remove the delivery filter.</p></div>}
  </main></>;
}
