import { useState } from "react";
import { Swiper } from "swiper/react";

export function BadHero({ product, onBuy }) {
  const [msg, setMsg] = useState("");
  return (
    <div>
      <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
      <nav>
        <a href="#" onClick={() => history.push("/breads")}>Breads</a>
        <a href="/about" aria-expanded="false">About</a>
        <ul role="menu">
          <li role="menuitem"><a href="/story">Story</a></li>
        </ul>
      </nav>
      <div onClick={onBuy} className="buy-tile focus:outline-none">
        Buy now
      </div>
      <span tabIndex={0} className="order-2 flex-row-reverse">Details</span>
      <img src={product.image} alt={product.image} />
      <img src="hero.png" alt="hero.png" />
      <button onMouseDown={onBuy}><CartIcon /></button>
      <input placeholder="Email" />
      <video autoPlay src="promo.mp4" />
      <audio autoPlay src="jingle.mp3" />
      <Swiper autoplay={{ delay: 3000 }} />
      <div style={{ order: 3 }} tabIndex={5}>Third</div>
      {msg && <div role="status">{msg}</div>}
      <a onClick={() => setMsg("hi")}>Open</a>
      <button autoFocus>Go</button>
      <a href="/menu.pdf">Menu (PDF)</a>
      <div dangerouslySetInnerHTML={{ __html: product.body }} />
    </div>
  );
}
