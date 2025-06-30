<?php
// Selected variable (default: wind_speed)
$var = $_GET['var'] ?? 'wind_speed';

// Load JSON data
$data = json_decode(file_get_contents('nmea_data.json'), true);

// Get series for the selected variable
$series = $data[$var] ?? [];

// Filter to last 10 minutes
$now = strtotime("now");
$filtered = array_filter($series, function($row) use ($now) {
    return strtotime($row[0]) >= $now - 600; // last 10 minutes
});

// Sort by time descending
usort($filtered, fn($a, $b) => strtotime($b[0]) <=> strtotime($a[0]));

// Get latest value
$latest = $filtered[0][1] ?? 'N/A';

// Get 1-minute average
$avg_data = array_filter($filtered, fn($r) => strtotime($r[0]) >= $now - 60);
$avg = count($avg_data) ? round(array_sum(array_column($avg_data, 1)) / count($avg_data), 2) : 'N/A';

// Get list of variables
$variables = array_keys($data);
?>
<!DOCTYPE html>
<html>
<head>
    <title>NMEA Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/luxon@3"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-luxon@1"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>

    <meta http-equiv="refresh" content="30">
    <style>
        body { font-family: sans-serif; margin: 0; padding: 1em; }
        h1, h2 { margin: 0.2em 0; }
        canvas { width: 100vw; height: 90vh !important; }
    </style>
</head>
<body>
    <h1>NMEA Dashboard: <?= htmlspecialchars($var) ?></h1>
    <h2>Latest: <?= $latest ?> &nbsp; | &nbsp; 1-min avg: <?= $avg ?></h2>

    <form method="get">
        <label for="var">Select variable:</label>
        <select name="var" id="var" onchange="this.form.submit()">
            <?php foreach ($variables as $v): ?>
                <option value="<?= $v ?>" <?= $v === $var ? 'selected' : '' ?>><?= $v ?></option>
            <?php endforeach; ?>
        </select>
    </form>

    <canvas id="chart"></canvas>

    <script>
        const raw = <?= json_encode($filtered) ?>;
        const labels = raw.map(row => row[0]);
        const values = raw.map(row => row[1]);

        new Chart(document.getElementById('chart'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: '<?= htmlspecialchars($var) ?>',
                    data: values,
                    borderColor: 'blue',
                    tension: 0.1,
                    pointRadius: 0
                }]
            },
            options: {
                indexAxis: 'y', // vertical strip chart
                scales: {
                    y: {
                        type: 'time',
                        time: {
                            unit: 'minute',
                            tooltipFormat: 'HH:mm:ss',
                            displayFormats: { minute: 'HH:mm' }
                        },
                        reverse: true
                    }
                },
                animation: false,
                responsive: true,
                plugins: {
                    legend: { display: false }
                }
            }
        });
    </script>
</body>
</html>

