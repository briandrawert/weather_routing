<?php

define('TAIL_NL', "\n");


/**
 * Tail in PHP, capable of eating big files.
 *
 * @author  Torleif Berger
 * @link    http://www.geekality.net/?p=1654
 */
function read_last_line($filename, $lines = 10, $buffer = 4096)
{
    // Open the file
    $f = fopen($filename, 'rb');

    echo("opened file $filename");
    // Jump to last character
    fseek($f, -1, SEEK_END);

    // Prepare to collect output
    $output = '';
    $chunk = '';

    // Start reading it and adjust line number if necessary
    // (Otherwise the result would be wrong if file doesn't end with a blank line)
    if(fread($f, 1) != TAIL_NL) $lines -= 1;

    // While we would like more
    while(ftell($f) > 0 && $lines >= 0)
    {
        // Figure out how far back we should jump
        $seek = min(ftell($f), $buffer);

        // Do the jump (backwards, relative to where we are)
        fseek($f, -$seek, SEEK_CUR);

        // Read a chunk and prepend it to our output
        $output = ($chunk = fread($f, $seek)).$output;

        // Jump back to where we started reading
        fseek($f, -strlen($chunk), SEEK_CUR);

        // Decrease our line counter
        $lines -= substr_count($chunk, TAIL_NL);
    }

    // While we have too many lines
    // (Because of buffer size we might have read too many)
    while($lines++ < 0)
    {
        // Find first newline and remove all text before that
        $output = substr($output, strpos($output, TAIL_NL) + 1);
    }

    // Close file and return
    fclose($f);
    return $output;
}
