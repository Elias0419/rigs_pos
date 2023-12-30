const socket = io();

// Function to add an item to the order
function addItem() {
    let barcode = document.getElementById('barcode-input').value;
    fetch('/add-item', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ barcode: barcode })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateOrderDetails(data.item.name, data.item.price);
        } else {
            alert('Item not found');
        }
    })
    .catch(error => console.error('Error:', error));
}

// Function to handle checkout
function checkout() {
    fetch('/checkout')
    .then(response => response.json())
    .then(data => {
        alert(`Total amount with tax: ${data.total}`);
        // Reset the order details on the page
        document.getElementById('order-details').innerHTML = '';
    })
    .catch(error => console.error('Error:', error));
}

// Socket.IO event listeners
socket.on('item_details', (data) => {
    updateOrderDetails(data.name, data.price);
});

socket.on('item_not_found', (data) => {
    alert(`Item with barcode ${data.barcode} not found`);
});

// Helper function to update order details on the page
function updateOrderDetails(name, price) {
    const orderDiv = document.getElementById('order-details');
    orderDiv.innerHTML += `<p>Item: ${name}, Price: ${price}</p>`;
}
