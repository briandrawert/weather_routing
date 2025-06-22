<?php

require('lib_tail.php');

date_default_timezone_set('UTC');  // Set your preferred timezone






$log_dir = '/home/brian/gps_logger';  // Adjust if needed
$filename = date('Y-m-d') . '.log';
$filepath = $log_dir . '/' . $filename;

if (!file_exists($filepath)) {
    echo "Log file not found: $filepath";
    exit;
}

#// Efficient way to get the last non-empty line
#$fp = fopen($filepath, 'r');
#$last_line = '';
#while (($line = fgets($fp)) !== false) {
#    $line = trim($line);
#    if ($line !== '') {
#        $last_line = $line;
#    }
#}
#fclose($fp);
#echo($filepath);
echo('<br>');
$last_line = read_last_line($filepath);

echo "<pre>Last GPS Log Entry:\n" . htmlspecialchars($last_line) . "</pre>";
?>

