async function fetchAndDisplayData() {
    let data = await eel.get_order_history_for_eel()();
    console.log(data)
    data = data.map(order => ({
        ...order,
        items: JSON.parse(order.items)
    }));


    const dailyTotals = data.reduce((acc, order) => {
    // Extract the date part from the timestamp
    const date = order.timestamp.split(' ')[0]; // Gets the date in 'YYYY-MM-DD' format
    // Initialize the daily total for the date if it doesn't exist
    if (!acc[date]) {
        acc[date] = 0;
    }
    // Add the total_with_tax of the current order to its respective date
    acc[date] += order.total_with_tax;
    return acc;
}, {});

// Step 3: Prepare the data structure for Chart.js
const labels = Object.keys(dailyTotals).sort(); // Sort the dates to display them in order
const datasetData = labels.map(label => dailyTotals[label]);

const chartData = {
    labels,
    datasets: [{
        label: 'Daily Sales Total',
        data: datasetData,
        backgroundColor: 'rgba(54, 162, 235, 0.2)',
        borderColor: 'rgba(54, 162, 235, 1)',
        borderWidth: 1
    }]
};

     // total with tax by order id example
    // const chartData = {
    //     labels: data.map(order => order.order_id),
    //     datasets: [{
    //         label: 'Total with Tax',
    //         data: data.map(order => order.total_with_tax),
    //         backgroundColor: 'rgba(54, 162, 235, 0.2)',
    //         borderColor: 'rgba(54, 162, 235, 1)',
    //         borderWidth: 1
    //     }]
    // };


    const ctx = document.getElementById('chart').getContext('2d');


    const myChart = new Chart(ctx, {
        type: 'bar',
        data: chartData,
        options: {
            scales: {
                y: {
                    beginAtZero: true
                }
            },
            plugins: {
                legend: {
                    display: true
                }
            }
        }
    });
}
fetchAndDisplayData();
