<?php
$variable = $_GET['var'] ?? 'wind_speed';
$avg_window = intval($_GET['avg'] ?? 60);  // in seconds
$json_path = '/var/www/html/nmea_data.json';

header("Refresh: 5");

function read_data($path) {
    if (!file_exists($path)) return [];
    $raw = file_get_contents($path);
    return json_decode($raw, true);
}

function moving_average($data, $window) {
    $recent = array_slice($data, -$window);
    $values = array_column($recent, 1);
    return count($values) ? array_sum($values) / count($values) : null;
}

$data = read_data($json_path);
$entries = $data[$variable] ?? [];
$latest = end($entries);
$avg = moving_average($entries, $avg_window);

// Generate strip chart (SVG)
$svg = '';
if ($entries) {
    $values = array_column($entries, 1);
    $min = min($values);
    $max = max($values);
    $height = 200;
    $width = 300;
    $svg = "<svg width=\"$width\" height=\"$height\">";
    $step = $width / count($entries);
    $x = 0;
    foreach ($values as $v) {
        $y = $height - (($v - $min) / ($max - $min + 0.0001) * $height);
        $svg .= "<line x1=\"$x\" y1=\"$height\" x2=\"$x\" y2=\"$y\" stroke=\"blue\" />";
        $x += $step;
    }
    $svg .= "</svg>";
}
?>
<!DOCTYPE html>
<html>
<head>
    <title>NMEA Live Monitor</title>
</head>
<body>
    <h2>NMEA Live Variable: <?= htmlspecialchars($variable) ?></h2>
    <form method="get">
        <label>Variable:
            <select name="var">
                <option value="wind_speed" <?= $variable == 'wind_speed' ? 'selected' : '' ?>>Wind Speed</option>
                <option value="sog" <?= $variable == 'sog' ? 'selected' : '' ?>>Speed Over Ground</option>
            </select>
        </label>
        <label>Avg (sec):
            <input type="number" name="avg" value="<?= $avg_window ?>" min="1" max="600">
        </label>
        <input type="submit" value="Update">
    </form>

    <p><strong>Latest:</strong> <?= $latest[1] ?? 'N/A' ?> at <?= $latest[0] ?? 'N/A' ?></p>
    <p><strong><?= $avg_window ?> sec avg:</strong> <?= round($avg, 2) ?></p>

    <?= $svg ? "<h3>Last 10 Minutes</h3>$svg" : "<p>No data available</p>" ?>
</body>
</html>

