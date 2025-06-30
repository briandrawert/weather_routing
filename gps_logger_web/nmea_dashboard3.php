<?php
$var = $_GET['var'] ?? 'sog';
$data = json_decode(file_get_contents('nmea_data.json'), true);
$points = $data[$var] ?? [];
?>

<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title><?= htmlspecialchars($var) ?> Chart</title>
  <style>
    body { margin: 0; }
    canvas { width: 100vw !important; height: 100vh !important; }
  </style>

  <!-- Load Luxon and Adapter BEFORE Chart.js -->
  <script src="https://cdn.jsdelivr.net/npm/luxon@3.4.4/build/global/luxon.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-luxon@1.3.0/dist/chartjs-adapter-luxon.umd.min.js"></script>
</head>
<body>
<canvas id="chart"></canvas>

<script>
const raw = <?= json_encode($points) ?>;
const labels = raw.map(r => r[0]);
const values = raw.map(r => r[1]);

const ctx = document.getElementById('chart').getContext('2d');

new Chart(ctx, {
  type: 'line',
  data: {
    labels: labels,
    datasets: [{
      label: '<?= htmlspecialchars($var) ?>',
      data: values,
      borderColor: 'blue',
      backgroundColor: 'rgba(0, 0, 255, 0.1)',
      tension: 0.2,
      pointRadius: 0
    }]
  },
  options: {
    responsive: true,
    animation: false,
    scales: {
      x: {
        type: 'time',
        time: {
          tooltipFormat: 'HH:mm:ss',
          displayFormats: { second: 'HH:mm:ss', minute: 'HH:mm' }
        },
        title: { display: true, text: 'Time' }
      },
      y: {
        title: { display: true, text: '<?= htmlspecialchars($var) ?>' }
      }
    },
    plugins: {
      legend: { display: false }
    }
  }
});
</script>
</body>
</html>

