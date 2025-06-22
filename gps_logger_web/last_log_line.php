<?php
date_default_timezone_set('UTC');  // Set your preferred timezone

$log_dir = '/home/brian/gps_logger';  // Change if your logs are stored elsewhere
$filename = date('Y-m-d') . '.log';
$filepath = $log_dir . '/' . $filename;

if (!file_exists($filepath)) {
    echo "Log file not found: $filepath";
    exit;
}

// Read last non-empty line
$lines = file($filepath, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
$last_line = end($lines);

echo "<pre>Last GPS Log Entry:<br>" . htmlspecialchars($last_line) . "</pre>";
?>

