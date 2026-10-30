import Link from 'next/link';
import {ArrowRight, MapPin, Search, ShoppingBasket, UtensilsCrossed, Sprout, Hammer, Store, Truck, ShieldCheck} from 'lucide-react';
import {Nav} from '@/components/Nav';

const categories = [
  {name:'Food & kitchens', icon:UtensilsCrossed, description:'Meals made nearby'},
  {name:'Groceries', icon:ShoppingBasket, description:'Everyday essentials'},
  {name:'Farm supplies', icon:Sprout, description:'Grow with your community'},
  {name:'Hardware', icon:Hammer, description:'Tools and home needs'},
  {name:'Local shops', icon:Store, description:'Your trusted neighbours'},
];
const benefits = [
  {name:'Shop your neighbourhood', icon:MapPin, detail:'Discover nearby stores using familiar areas and landmarks.'},
  {name:'Local delivery', icon:Truck, detail:'Get essentials delivered where service is available.'},
  {name:'Shop with confidence', icon:ShieldCheck, detail:'Review availability and order details before checkout.'},
];

export default function Home() {
  return <><Nav/><main>
    <section className="gaonHero">
      <div className="container gaonHeroInner">
        <div className="gaonHeroCopy">
          <span className="gaonKicker">MADE FOR EVERY NEIGHBOURHOOD</span>
          <h1>Your whole local market, <em>one happy place.</em></h1>
          <p>From hot meals to fresh vegetables, groceries and farm supplies—discover the shops that make your neighbourhood special.</p>
          <div className="gaonHeroActions">
            <Link href="/market" className="gaonPrimary">Explore the marketplace <ArrowRight size={19}/></Link>
            <Link href="/login" className="gaonSecondary">Sign in</Link>
          </div>
          <div className="gaonHeroHint"><MapPin size={18}/> Choose your area or landmark to find available stores.</div>
        </div>
        <div className="gaonHeroArt" aria-label="Illustration of local shopping">
          <div className="gaonArtBadge">Fresh picks from nearby stores</div>
          <div className="gaonArtCenter"><ShoppingBasket size={78} strokeWidth={1.5}/><strong>Discover local goodness</strong><span>Food · Groceries · More</span></div>
          <div className="gaonArtBubble bubbleOne"><Sprout size={28}/> Fresh</div>
          <div className="gaonArtBubble bubbleTwo"><Truck size={28}/> Local delivery</div>
        </div>
      </div>
    </section>
    <section className="container gaonExplore">
      <div className="gaonSectionTitle"><div><span className="gaonKicker">DISCOVER GAONONE</span><h2>What are you looking for?</h2></div><Link href="/market">View all stores <ArrowRight size={17}/></Link></div>
      <Link href="/market" className="gaonSearchLink"><Search size={22}/><span>Search for products, stores and nearby essentials</span><ArrowRight size={19}/></Link>
      <div className="gaonCategoryGrid">{categories.map(({name,icon:Icon,description})=><Link href="/market" className="gaonCategory" key={name}><span className="gaonCategoryIcon"><Icon size={30}/></span><strong>{name}</strong><small>{description}</small><ArrowRight size={18} className="gaonCategoryArrow"/></Link>)}</div>
    </section>
    <section className="gaonWhy"><div className="container"><div className="gaonSectionTitle"><div><span className="gaonKicker">BUILT AROUND YOU</span><h2>Local shopping, made simpler.</h2></div></div><div className="gaonBenefitGrid">{benefits.map(({name,icon:Icon,detail})=><article className="gaonBenefit" key={name}><Icon size={30}/><h3>{name}</h3><p>{detail}</p></article>)}</div></div></section>
  </main></>;
}
