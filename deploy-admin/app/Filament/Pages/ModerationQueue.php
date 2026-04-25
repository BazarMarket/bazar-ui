<?php

namespace App\Filament\Pages;

use Filament\Pages\Page;
use Filament\Navigation\NavigationItem;

class ModerationQueue extends Page
{
    protected static string $view = 'filament.pages.moderation-queue';

    public array $items = [];
    public int $pendingCount = 0;
    public string $flash = '';
    public string $flashType = '';

    private function pythonUrl(): string
    {
        return rtrim(env('BAZAR_PYTHON_URL', 'http://127.0.0.1:5000'), '/');
    }

    public function mount(): void
    {
        $this->loadQueue();
    }

    public function loadQueue(): void
    {
        try {
            $url      = $this->pythonUrl() . '/api/moderation/queue';
            $context  = stream_context_create(['http' => ['timeout' => 5, 'ignore_errors' => true]]);
            $response = file_get_contents($url, false, $context);
            if ($response !== false) {
                $data             = json_decode($response, true) ?? [];
                $this->items      = $data['items']        ?? [];
                $this->pendingCount = $data['pending_count'] ?? 0;
            }
        } catch (\Throwable $e) {
            $this->items = [];
        }
    }

    public function approve(int $id): void
    {
        $this->callPython('/api/moderation/approve', ['id' => $id]);
        $this->flash     = 'Approved — ad is now active.';
        $this->flashType = 'success';
        $this->loadQueue();
    }

    public function reject(int $id): void
    {
        $this->callPython('/api/moderation/reject', ['id' => $id]);
        $this->flash     = 'Rejected — ad set to inactive.';
        $this->flashType = 'danger';
        $this->loadQueue();
    }

    private function callPython(string $path, array $payload): void
    {
        try {
            $url     = $this->pythonUrl() . $path;
            $data    = json_encode($payload);
            $context = stream_context_create([
                'http' => [
                    'method'        => 'POST',
                    'header'        => "Content-Type: application/json\r\nContent-Length: " . strlen($data) . "\r\n",
                    'content'       => $data,
                    'timeout'       => 5,
                    'ignore_errors' => true,
                ],
            ]);
            file_get_contents($url, false, $context);
        } catch (\Throwable $e) {
        }
    }

    public static function getNavigationItems(): array
    {
        $pending = 0;
        try {
            $url      = rtrim(env('BAZAR_PYTHON_URL', 'http://127.0.0.1:5000'), '/') . '/api/moderation/queue';
            $context  = stream_context_create(['http' => ['timeout' => 2, 'ignore_errors' => true]]);
            $response = file_get_contents($url, false, $context);
            if ($response !== false) {
                $data    = json_decode($response, true) ?? [];
                $pending = $data['pending_count'] ?? 0;
            }
        } catch (\Throwable $e) {
        }

        $label = $pending > 0 ? "AI Moderation ({$pending})" : 'AI Moderation';

        return [
            NavigationItem::make($label)
                ->group('Moderation')
                ->icon('heroicon-o-shield-exclamation')
                ->url(static::getUrl())
                ->isActiveWhen(fn () => request()->routeIs(static::getRouteName()))
                ->sort(1),
        ];
    }

    public static function getSlug(): string
    {
        return 'moderation-queue';
    }
}
