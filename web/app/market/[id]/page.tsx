'use client';

import {useEffect, useMemo, useRef, useState} from 'react';
import Link from 'next/link';
import {useParams} from 'next/navigation';
import {Clock3, MapPin, Minus, Plus, Search, ShoppingCart, Truck} from 'lucide-react';
import {gaonApi, Store, StoreProduct, Substitution} from '@/lib/api';
import {Nav} from '@/components/Nav';
import {SubstitutionChoices} from '@/components/SubstitutionChoices';

const money = (value: string | number) => new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR'}).format(Number(value));

export default function StorePage() {
  const {id} = useParams<{id: string}>();
  const [store, setStore] = useState<Store | null>(null);
  const [items, setItems] = useState<StoreProduct[]>([]);
  const [approvedImages, setApprovedImages] = useState<Record<string, string>>({});
  const [qty, setQty] = useState<Record<string, number>>({});
  const [q, setQ] = useState('');
  const [msg, setMsg] = useState('');
  const [cartCount, setCartCount] = useState(0);
  const [busy, setBusy] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [loadedStoreId, setLoadedStoreId] = useState<string | null>(null);
  const loadRequest = useRef(0);
  const cartRequest = useRef(0);
  const cartMutationInFlight = useRef(false);
  const hasLoadedStorefront = loadedStoreId === id;

  async function loadStorefront() {
    const requestId = ++loadRequest.current;
    setLoading(true);
    setLoadError('');
    try {
      const [nextStore, nextItems] = await Promise.all([gaonApi.store(id), gaonApi.storeProducts(id)]);
      if (requestId !== loadRequest.current) return;
      setStore(nextStore);
      setItems(nextItems);
      setLoadedStoreId(id);
      // Optional media must never block the catalogue or checkout.
      setApprovedImages({});
      void gaonApi.approvedStoreImages(id).then(images => {
        if (requestId !== loadRequest.current) return;
        const urls: Record<string, string> = {};
        for (const [listingId, assets] of Object.entries(images)) {
          const first = assets.find(asset => asset.url.startsWith('https://'));
          if (first) urls[listingId] = first.url;
        }
        setApprovedImages(urls);
      }).catch(() => {
        if (requestId === loadRequest.current) setApprovedImages({});
      });
    } catch (error: unknown) {
      if (requestId !== loadRequest.current) return;
      setLoadError(error instanceof Error ? error.message : 'Storefront is temporarily unavailable.');
    } finally {
      if (requestId === loadRequest.current) setLoading(false);
    }
  }

  async function loadCartCount() {
    const requestId = ++cartRequest.current;
    try {
      const cart = await gaonApi.cart();
      if (requestId === cartRequest.current) setCartCount(cart.items.reduce((count, item) => count + item.quantity, 0));
    } catch {
      // The store and catalogue stay useful when only the optional cart badge cannot refresh.
    }
  }

  useEffect(() => {
    void loadStorefront();
    void loadCartCount();
    return () => {
      loadRequest.current += 1;
      cartRequest.current += 1;
    };
  }, [id]);

  const shown = useMemo(() => items.filter(item => {
    const text = `${item.product.name} ${item.product.brand || ''} ${item.product.description || ''}`.toLowerCase();
    return text.includes(q.toLowerCase());
  }), [items, q]);

  function amount(product: StoreProduct) {
    return Math.min(qty[product.id] || 1, product.stock_quantity);
  }

  function beginCartMutation(listingId: string) {
    if (cartMutationInFlight.current) return false;
    cartMutationInFlight.current = true;
    // State keeps controls and feedback honest; the ref is the synchronous
    // guard for events delivered before React can render that state.
    setBusy(listingId);
    // An in-flight badge read cannot replace the cart returned by this write.
    cartRequest.current += 1;
    return true;
  }

  function finishCartMutation() {
    cartMutationInFlight.current = false;
    setBusy('');
  }

  async function addListing(listingId: string, quantity: number, successMessage: string) {
    if (!beginCartMutation(listingId)) return false;
    try {
      const cart = await gaonApi.addCart(listingId, quantity);
      setCartCount(cart.items.reduce((count, item) => count + item.quantity, 0));
      setMsg(successMessage);
      return true;
    } catch (error: unknown) {
      if (error instanceof Error && 'status' in error && error.status === 401) setMsg('Sign in to add items.');
      else setMsg(error instanceof Error ? error.message : 'Unable to add this item.');
      return false;
    } finally {
      finishCartMutation();
    }
  }

  async function add(product: StoreProduct) {
    // Capture the selected quantity before awaiting the authoritative response.
    const quantity = amount(product);
    return addListing(product.id, quantity, `${quantity} × ${product.product.name} added to cart.`);
  }

  async function addSubstitution(item: Substitution) {
    return addListing(item.listing_id, 1, 'Chosen alternative added to cart.');
  }

  return <><Nav /><main className="container section customerMarket customerStorefront" aria-busy={loading || Boolean(busy)}>
    {loading && !hasLoadedStorefront && !loadError && <p className="muted" role="status">Loading store catalogue…</p>}
    {loadError && <div className="notice" role="alert"><span>{hasLoadedStorefront ? 'Unable to refresh this storefront. Showing the last confirmed catalogue. ' : 'Unable to load this storefront. '}{loadError}</span><button type="button" className="btn secondary" disabled={loading} onClick={() => void loadStorefront()}>Retry storefront</button></div>}
    {hasLoadedStorefront && store && <>
      <div className="storeHero"><div><span className="eyebrow">Verified local storefront</span><h2>{store.name}</h2><p className="muted">{store.description || 'Local essentials available around your area.'}</p><div className="row muted" style={{flexWrap: 'wrap'}}><span className={`badge status-${store.is_open_now ? 'approved' : 'cancelled'}`}>{store.is_open_now ? 'Open now' : 'Closed now'}</span>{store.landmark && <span className="row"><MapPin size={15} />{store.landmark}</span>}{(store.opens_at || store.closes_at) && <span className="row"><Clock3 size={15} />{store.opens_at?.slice(0, 5) || '—'}–{store.closes_at?.slice(0, 5) || '—'} IST</span>}{store.delivery_enabled && <span className="row"><Truck size={15} /> Doorstep delivery</span>}</div></div><div className="row"><button type="button" className="btn secondary" disabled={loading} onClick={() => void loadStorefront()}>Refresh storefront</button><Link href="/cart" className="btn"><ShoppingCart size={17} /> Cart {cartCount > 0 && `(${cartCount})`}</Link></div></div>
      {loading && <p className="muted" role="status">Refreshing store catalogue…</p>}
      {msg && <div className="notice" role="status">{msg}</div>}
      <div className="panel filterBar"><div className="search" style={{flex: 1}}><Search size={18} /><input aria-label="Search store catalogue" value={q} onChange={event => setQ(event.target.value)} placeholder="Search products in this store..." /></div><span className="badge">{shown.length} available</span></div>
      <div className="grid productGrid" style={{marginTop: 20}}>{shown.map(product => {
        const discount = product.mrp ? Math.max(0, Math.round((1 - Number(product.price) / Number(product.mrp)) * 100)) : 0;
        return <div className="card productCard" key={product.id}><div className="row space"><span className="pill">{product.product.unit}</span>{discount > 0 && <span className="badge status-approved">{discount}% off</span>}</div>{approvedImages[product.id] && <div className="approvedProductImage"><img src={approvedImages[product.id]} alt={product.product.name} loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={event => { event.currentTarget.style.display = 'none'; }} /></div>}<h3>{product.product.name}</h3><p className="muted clamp2">{product.product.brand || product.product.description || 'Local catalogue item'}</p><div><span className="price">{money(product.price)}</span>{product.mrp && Number(product.mrp) > Number(product.price) && <span className="muted strike">{money(product.mrp)}</span>}</div><div className="row space" style={{marginTop: 14}}><div className="qtyControl"><button type="button" className="qtyBtn" aria-label={`Decrease ${product.product.name} quantity`} onClick={() => setQty(current => ({...current, [product.id]: Math.max(1, amount(product) - 1)}))}><Minus size={14} /></button><strong aria-label={`${product.product.name} quantity`}>{amount(product)}</strong><button type="button" className="qtyBtn" aria-label={`Increase ${product.product.name} quantity`} disabled={amount(product) >= product.stock_quantity} onClick={() => setQty(current => ({...current, [product.id]: Math.min(product.stock_quantity, amount(product) + 1)}))}><Plus size={14} /></button></div><button type="button" className="btn" disabled={Boolean(busy)} onClick={() => void add(product)}><ShoppingCart size={16} /> {busy === product.id ? 'Adding…' : 'Add'}</button></div><p className={`stockText ${product.stock_quantity <= 5 ? 'lowStock' : ''}`}>{product.stock_quantity <= 5 ? `Only ${product.stock_quantity} left` : `${product.stock_quantity} in stock`}</p>{product.stock_quantity <= 5 && <SubstitutionChoices listingId={product.id} onChoose={addSubstitution} cartBusy={Boolean(busy)} />}</div>;
      })}</div>
      {!loading && shown.length === 0 && <div className="panel emptyState"><h3>No matching products</h3><p className="muted">Try a different search term.</p></div>}
    </>}
  </main></>;
}
