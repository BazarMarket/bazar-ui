<?php

use Illuminate\Http\Request;

define('LARAVEL_START', microtime(true));

if (file_exists($maintenance = __DIR__.'/../storage/framework/maintenance.php')) {
    require $maintenance;
}

// Load shared vendor autoloader (vendor/ is symlinked to prod)
$loader = require_once __DIR__.'/../vendor/autoload.php';

// CRITICAL: vendor/ is symlinked from prod, so Composer's autoloader maps
// App\ namespace → /var/www/bazar-dev/app/ (prod). Override PSR-4 so that
// App\ classes load from THIS dev-admin app/ directory instead.
$loader->setPsr4('App\\', [dirname(__DIR__) . '/app']);

$app = require_once __DIR__.'/../bootstrap/app.php';

$kernel = $app->make(Illuminate\Contracts\Http\Kernel::class);

$response = $kernel->handle(
    $request = Request::capture()
)->send();

$kernel->terminate($request, $response);
