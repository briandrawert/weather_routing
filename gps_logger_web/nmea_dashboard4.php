<?php
// Read selected variable from URL or default to sog
$var = $_GET['var'] ?? 'sog';

// Load JSON data
$data = json_decode(file_get_contents('nmea_data.json'), true);
$points = $data[$var] ?? [];

// Get available variables for dropdown
$variables = array_keys($data);
$latest_value = count($points) ? end($points)[1] : 'N/A';
?>

<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>NMEA Dashboard</title>
  <style>
    body {
      margin: 0;
      font-family: sans-serif;
      background: #111;
      color: #fff;
    }
    header {
      padding: 1em;
      background: #222;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    select, h1 {
      font-size: 1.5em;
    }
    #latest {
      font-size: 2em;
      font-weight: bold;
    }
    canvas {
      width: 100vw !important;
      height: calc(100vh - 80px) !important;
    }
  </style>

  <!-- Load required JS -->
  <script src="https://cdn.jsdelivr.net/npm/luxon@3.4.4/build/global/luxon.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-luxon@1.3.0/dist/chartjs-adapter-luxon.umd.min.js"></script>

  <!-- Auto-refresh every 5 seconds -->
  <meta http-equiv="refresh" content="5">
</head>
<body>
  <header>
    <form method="get">
      <label for="var">Variable:</label>
      <select name="var" id="var" onchange="this.form.submit()">
        <?php foreach ($variables as $v): ?>
          <option value="<?= htmlspecialchars($v) ?>" <?= $v === $var ? 'selected' : '' ?>><?= htmlspecialchars($v) ?></option>
        <?php endforeach; ?>
      </select>
    </form>
    <div id="latest"><?= htmlspecialchars(strtoupper($var)) ?>: <?= htmlspecialchars($latest_value) ?></div>
  </header>

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
          borderColor: 'lime',
          backgroundColor: 'rgba(0,255,0,0.1)',
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

