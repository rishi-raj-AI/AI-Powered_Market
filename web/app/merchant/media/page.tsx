'use client';

import {useEffect, useState} from 'react';
import Link from 'next/link';
import {Nav} from '@/components/Nav';
import {api, gaonApi, getToken, type Store, type StoreProduct} from '@/lib/api';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
type MediaAsset = {id: string; state: string; alt_text: string | null; position: number; is_primary: boolean; created_at: string};
type QueuedAsset = {id: string; state: string};

export default function MerchantMedia() {
  const [stores, setStores] = useState<Store[]>([]);
  const [storeId, setStoreId] = useState('');
  const [inventory, setInventory] = useState<StoreProduct[]>([]);
  const [listingId, setListingId] = useState('');
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [statusLoading, setStatusLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    let active = true;
    gaonApi.myStores().then(items => {
      if (!active) return;
      setStores(items);
      setStoreId(items[0]?.id || '');
      setLoading(false);
    }).catch((e: Error) => {
      if (active) { setError(e.message); setLoading(false); }
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setInventory([]);
    setListingId('');
    setAssets([]);
    setFile(null);
    setNotice('');
    if (!storeId) return;
    gaonApi.storeInventory(storeId).then(items => {
      if (!active) return;
      setInventory(items);
      setListingId(items[0]?.id || '');
    }).catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [storeId]);

  useEffect(() => {
    let active = true;
    setAssets([]);
    setNotice('');
    if (!listingId) return;
    setStatusLoading(true);
    api<MediaAsset[]>('/media/store-products/' + listingId + '/images')
      .then(items => { if (active) setAssets(items); })
      .catch((e: Error) => { if (active) setError(e.message); })
      .finally(() => { if (active) setStatusLoading(false); });
    return () => { active = false; };
  }, [listingId]);

  useEffect(() => {
    if (!file) { setPreview(''); return; }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  async function refresh() {
    if (!listingId) return;
    setStatusLoading(true);
    setError('');
    try {
      setAssets(await api<MediaAsset[]>('/media/store-products/' + listingId + '/images'));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unable to refresh image status');
    } finally { setStatusLoading(false); }
  }

  async function upload() {
    if (!file || !listingId || busy) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setError('Select a JPEG, PNG or WebP image.'); return;
    }
    const token = getToken();
    if (!token) { setError('Sign in as the store owner to upload images.'); return; }
    setBusy(true); setError(''); setNotice('');
    try {
      const form = new FormData();
      form.append('file', file);
      const response = await fetch(API + '/media/store-products/' + listingId + '/images', {
        method: 'POST', headers: {Authorization: 'Bearer ' + token}, body: form,
      });
      const body = await response.json();
      if (!response.ok) {
        if (response.status === 503) throw new Error('Secure product image processing is not enabled. Ask the administrator to configure it.');
        throw new Error(typeof body.detail === 'string' ? body.detail : 'Image upload failed (' + response.status + ')');
      }
      const queued = body as QueuedAsset;
      if (response.status !== 202 || queued.state !== 'quarantined') {
        throw new Error('The image upload was not confirmed as quarantined. Refresh before trying again.');
      }
      setNotice('Image queued for safety checks. It will appear in the marketplace only after approval.');
      setFile(null);
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Image upload failed');
    } finally { setBusy(false); }
  }

  return <><Nav/><main className="container section">
    <span className="eyebrow">Merchant catalog</span>
    <h2>Product photos</h2>
    <p className="muted">Choose a product listing before uploading. Images are privately quarantined, checked and processed before any approved version is published. Raw uploads are never public.</p>
    {error && <div className="notice" role="alert">{error}</div>}
    {notice && <div className="notice" role="status">{notice}</div>}
    {loading ? <p role="status">Loading your stores…</p> : stores.length === 0 ?
      <div className="panel">No storefronts found. <Link href="/merchant">Set up your store</Link> before uploading product photos.</div> :
      <div className="panel form" style={{maxWidth: 720}}>
        <div className="field"><label htmlFor="media-store">Store</label><select id="media-store" value={storeId} disabled={busy} onChange={e => setStoreId(e.target.value)}>{stores.map(store => <option key={store.id} value={store.id}>{store.name}</option>)}</select></div>
        <div className="field"><label htmlFor="media-listing">Product listing</label><select id="media-listing" value={listingId} onChange={e => {setListingId(e.target.value);setFile(null);}} disabled={inventory.length === 0 || busy}><option value="">Select product</option>{inventory.map(item => <option key={item.id} value={item.id}>{item.product.name} · {item.product.unit}</option>)}</select></div>
        {inventory.length === 0 && <p className="muted">Add a product to this store before uploading its photo.</p>}
        <div className="field"><label htmlFor="media-file">JPEG, PNG or WebP photo</label><input id="media-file" type="file" accept="image/jpeg,image/png,image/webp" disabled={!listingId || busy} onChange={e => setFile(e.target.files?.[0] || null)}/></div>
        {preview && <img src={preview} alt="Selected product photo preview" style={{maxWidth:'100%',maxHeight:260,objectFit:'contain'}}/>}
        <button type="button" className="btn" disabled={!listingId || !file || busy} onClick={upload}>{busy ? 'Uploading…' : 'Upload image'}</button>
      </div>}
    {listingId && <section className="section"><div className="panel"><div className="row space" style={{flexWrap:'wrap'}}><h3>Image processing status</h3><button type="button" className="btn secondary" disabled={statusLoading} onClick={refresh}>Refresh status</button></div>
      {statusLoading ? <p role="status">Loading image status…</p> : assets.length === 0 ? <p className="muted">No images have been submitted for this product.</p> :
      <ul>{assets.map(asset => <li key={asset.id}><strong>{asset.state === 'approved' ? 'Approved for display' : asset.state === 'rejected' ? 'Rejected' : 'Awaiting safety checks'}</strong> · {asset.state} · {new Date(asset.created_at).toLocaleDateString('en-IN')}</li>)}</ul>}
    </div></section>}
  </main></>;
}
