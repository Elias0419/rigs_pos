const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
let order = null;
let selectedMethod = 'Cash';

const $ = (id) => document.getElementById(id);

function setStatus(text, error = false) {
  const el = $('status');
  el.textContent = text;
  el.style.color = error ? 'var(--danger)' : 'var(--muted)';
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || 'Request failed');
  return payload;
}

function renderOrder(nextOrder) {
  order = nextOrder;
  $('orderId').textContent = order.order_id ? `#${order.order_id.slice(0, 8)}` : 'Ready';
  $('subtotal').textContent = money.format(order.subtotal || 0);
  $('discount').textContent = money.format(order.total_discount || 0);
  $('tax').textContent = money.format(order.tax_amount || 0);
  $('total').textContent = money.format(order.total_with_tax || 0);
  $('change').textContent = money.format(order.change_given || 0);
  if (!$('amountTendered').value && selectedMethod === 'Cash') {
    $('amountTendered').placeholder = (order.total_with_tax || 0).toFixed(2);
  }

  const items = Object.values(order.items || {});
  const container = $('orderItems');
  if (!items.length) {
    container.className = 'order-items empty';
    container.textContent = 'No items yet.';
    return;
  }
  container.className = 'order-items';
  container.innerHTML = items.map((item) => `
    <article class="order-line">
      <div>
        <strong>${escapeHtml(item.name)}</strong>
        <div class="line-meta">${money.format(item.price)} each · ${money.format(item.total_price)}</div>
      </div>
      <div class="line-controls">
        <button class="ghost" data-dec="${item.item_id}">−</button>
        <span class="qty">${item.quantity}</span>
        <button class="ghost" data-inc="${item.item_id}">+</button>
        <button class="ghost danger" data-remove="${item.item_id}">×</button>
      </div>
    </article>
  `).join('');
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[char]));
}

async function refreshOrder() {
  renderOrder(await api('/api/order'));
}

async function searchItems(query = '') {
  const result = await api(`/api/items/search?q=${encodeURIComponent(query)}&limit=30`);
  const box = $('searchResults');
  box.innerHTML = result.items.map((item) => `
    <article class="result">
      <div>
        <strong>${escapeHtml(item.name)}</strong><br />
        <small>${escapeHtml(item.barcode || '')} ${item.product_category ? '· ' + escapeHtml(item.product_category) : ''}</small>
      </div>
      <button data-add-item="${escapeHtml(item.item_id || '')}" data-barcode="${escapeHtml(item.barcode || '')}">${money.format(item.price || 0)}</button>
    </article>
  `).join('') || '<p class="hint">No matches.</p>';
}

$('scanForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const input = $('scanInput');
  const barcode = input.value.trim();
  if (!barcode) return;
  try {
    const result = await api('/api/order/scan', { method: 'POST', body: JSON.stringify({ barcode }) });
    renderOrder(result.order);
    setStatus(`Added ${result.item.name}`);
    input.value = '';
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    input.focus();
  }
});

$('searchInput').addEventListener('input', (event) => searchItems(event.target.value));

$('searchResults').addEventListener('click', async (event) => {
  const button = event.target.closest('[data-add-item]');
  if (!button) return;
  const result = await api('/api/order/items', {
    method: 'POST',
    body: JSON.stringify({ item_id: button.dataset.addItem, barcode: button.dataset.barcode }),
  });
  renderOrder(result.order);
  setStatus(`Added ${result.item.name}`);
  $('scanInput').focus();
});

$('orderItems').addEventListener('click', async (event) => {
  const inc = event.target.closest('[data-inc]');
  const dec = event.target.closest('[data-dec]');
  const remove = event.target.closest('[data-remove]');
  const id = inc?.dataset.inc || dec?.dataset.dec || remove?.dataset.remove;
  if (!id) return;
  const item = order.items[id];
  const quantity = inc ? item.quantity + 1 : dec ? item.quantity - 1 : 0;
  const result = quantity < 1
    ? await api(`/api/order/items/${encodeURIComponent(id)}`, { method: 'DELETE' })
    : await api(`/api/order/items/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ quantity }) });
  renderOrder(result);
});

document.querySelectorAll('.pay-method').forEach((button) => {
  button.addEventListener('click', () => {
    selectedMethod = button.dataset.method;
    document.querySelectorAll('.pay-method').forEach((b) => b.classList.toggle('selected', b === button));
    $('amountTendered').disabled = selectedMethod !== 'Cash';
  });
});

$('exactCash').addEventListener('click', () => {
  $('amountTendered').value = (order?.total_with_tax || 0).toFixed(2);
});

$('takePayment').addEventListener('click', async () => {
  try {
    const result = await api('/api/order/pay', {
      method: 'POST',
      body: JSON.stringify({ method: selectedMethod, amount_tendered: $('amountTendered').value }),
    });
    renderOrder(result);
    setStatus(`${selectedMethod} payment staged`);
  } catch (error) {
    setStatus(error.message, true);
  }
});

$('finalize').addEventListener('click', async () => {
  try {
    const result = await api('/api/order/finalize', { method: 'POST', body: JSON.stringify({}) });
    renderOrder(result.order);
    $('amountTendered').value = '';
    setStatus(`Finalized #${result.completed_order.order_id.slice(0, 8)}`);
  } catch (error) {
    setStatus(error.message, true);
  }
});

$('clearOrder').addEventListener('click', async () => {
  renderOrder(await api('/api/order/clear', { method: 'POST' }));
  $('amountTendered').value = '';
  setStatus('Order cleared');
  $('scanInput').focus();
});

refreshOrder();
searchItems('');
setTimeout(() => $('scanInput').focus(), 100);
