CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    in_stock INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    ordered_at TEXT NOT NULL
);

INSERT OR IGNORE INTO products (id, name, category, price_cents, in_stock) VALUES
    (1, 'Notebook', 'stationery', 499, 1),
    (2, 'Mechanical Keyboard', 'electronics', 12999, 1),
    (3, 'Desk Lamp', 'furniture', 4599, 0),
    (4, 'USB-C Hub', 'electronics', 3499, 1);

INSERT OR IGNORE INTO orders (id, product_id, quantity, ordered_at) VALUES
    (1, 2, 1, '2026-01-15'),
    (2, 1, 3, '2026-01-20'),
    (3, 4, 2, '2026-02-01');
