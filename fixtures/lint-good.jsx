export function GoodHero({ product, onBuy, announce }) {
  return (
    <div>
      <nav aria-label="Primary">
        <ul>
          <li><a href="/breads">Breads</a></li>
          <li>
            <button type="button" aria-expanded="false" aria-controls="nav-about">
              About
            </button>
            <ul id="nav-about" hidden>
              <li><a href="/about/story">Our story</a></li>
            </ul>
          </li>
        </ul>
      </nav>
      <a href={`/p/${product.slug}`}>
        <img src={product.imageUrl} alt="" />
        <h3>{product.name}</h3>
      </a>
      <button
        type="button"
        onClick={onBuy}
        className="rounded px-4 py-2 focus-visible:outline-2 focus-visible:outline-offset-2"
      >
        Add to cart
        <span className="sr-only">: {product.name}</span>
      </button>
      <label htmlFor="email">Email address</label>
      <input id="email" name="email" type="email" autoComplete="email" />
      <div role="status" className="sr-only">{""}</div>
    </div>
  );
}
