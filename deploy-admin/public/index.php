<?php

use Illuminate\Http\Request;

define('LARAVEL_START', microtime(true));

if (file_exists($maintenance = __DIR__.'/../storage/framework/maintenance.php')) {
    require $maintenance;
}

// Load shared vendor autoloader (vendor/ is symlinked to prod)
$loader = require_once __DIR__.'/../vendor/autoload.php';

// CRITICAL ISOLATION FIX:
// vendor/ is a symlink to prod. Composer maps ALL App\ classes (PSR-4 and
// classmap) to prod's app/ directory. Override BOTH to use dev-admin's app/.

$devAppPath  = dirname(__DIR__) . '/app';                // /var/www/bazar-dev-admin/app
$vendorReal  = realpath(dirname(__DIR__) . '/vendor');   // /var/www/bazar-dev/vendor (resolved)
$prodAppPath = dirname($vendorReal) . '/app';            // /var/www/bazar-dev/app

// 1. Override PSR-4
$loader->setPsr4('App\\', [$devAppPath]);

// 2. Override classmap — paths are non-normalized (contain ../../app/),
//    use realpath() to resolve them before comparing
$fixedMap = [];
foreach ($loader->getClassMap() as $class => $path) {
    if (strpos($class, 'App\\') === 0) {
        $real = realpath($path);
        if ($real && strpos($real, $prodAppPath) === 0) {
            $fixedMap[$class] = $devAppPath . substr($real, strlen($prodAppPath));
        }
    }
}
if ($fixedMap) {
    $loader->addClassMap($fixedMap);
}

$app = require_once __DIR__.'/../bootstrap/app.php';

$kernel = $app->make(Illuminate\Contracts\Http\Kernel::class);

$response = $kernel->handle(
    $request = Request::capture()
)->send();

$kernel->terminate($request, $response);
