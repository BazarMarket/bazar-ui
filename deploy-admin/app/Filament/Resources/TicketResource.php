<?php
namespace App\Filament\Resources;

use App\Models\Ticket;
use App\Models\TicketMessage;
use Filament\Resources\Resource;
use Filament\Tables\Table;
use Filament\Tables\Columns\TextColumn;
use Filament\Actions\Action;
use Filament\Actions\BulkActionGroup;
use Filament\Actions\DeleteBulkAction;
use Filament\Forms\Components\Textarea;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\Placeholder;
use Filament\Forms\Components\FileUpload;
use Filament\Notifications\Notification;
use Illuminate\Support\HtmlString;

class TicketResource extends Resource
{
    protected static ?string $model = Ticket::class;

    public static function getNavigationIcon(): string { return 'heroicon-o-ticket'; }
    public static function getNavigationLabel(): string { return 'Support Tickets'; }
    public static function getNavigationGroup(): ?string { return null; }
    public static function getNavigationSort(): ?int { return 3; }

    public static function getNavigationBadge(): ?string
    {
        $count = Ticket::whereIn('status', ['open', 'need_human'])->count();
        return $count > 0 ? (string)$count : null;
    }

    public static function getNavigationBadgeColor(): ?string { return 'danger'; }

    private static function pythonUrl(): string
    {
        return rtrim(env('BAZAR_PYTHON_URL', 'http://127.0.0.1:5000'), '/');
    }

    private static function getAiDraft(Ticket $record): string
    {
        try {
            $url  = self::pythonUrl() . '/api/admin/ticket-suggest';
            $data = json_encode(['ticket_id' => $record->id]);
            $ctx  = stream_context_create([
                'http' => [
                    'method'        => 'POST',
                    'header'        => "Content-Type: application/json\r\nContent-Length: " . strlen($data) . "\r\n",
                    'content'       => $data,
                    'timeout'       => 18,
                    'ignore_errors' => true,
                ],
            ]);
            $resp = @file_get_contents($url, false, $ctx);
            if (!$resp) return '';
            $json = json_decode($resp, true);
            return $json['suggestion'] ?? '';
        } catch (\Throwable $e) {
            return '';
        }
    }

    private static function buildThreadHtml(Ticket $record): string
    {
        $record->load('messages');
        $html = '<div style="display:flex;flex-direction:column;gap:12px;max-height:340px;overflow-y:auto;padding:2px 0;">';

        foreach ($record->messages as $msg) {
            $senderLabel = match($msg->sender_type) {
                'client' => '👤 Customer',
                'ai'     => '🤖 AI Assistant',
                'human'  => '✍️ Support Team',
                default  => $msg->sender_type,
            };
            $bg = match($msg->sender_type) {
                'client' => '#eff6ff',
                'ai'     => '#f0fdf4',
                'human'  => '#fffbeb',
                default  => '#f9fafb',
            };
            $color = match($msg->sender_type) {
                'client' => '#1d4ed8',
                'ai'     => '#15803d',
                'human'  => '#92400e',
                default  => '#374151',
            };
            $time = $msg->created_at ? $msg->created_at->format('d M Y H:i') : '';
            $msgText = $msg->message && $msg->message !== '(image)'
                ? '<p style="font-size:13px;line-height:1.65;color:#374151;margin:0 0 4px;white-space:pre-wrap;">' . e($msg->message) . '</p>'
                : '';

            $attachHtml = '';
            $atts = $msg->attachments ?? [];
            if (is_string($atts)) {
                $atts = json_decode($atts, true) ?: [];
            }
            if ($atts) {
                $attachHtml = '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;">';
                foreach ($atts as $url) {
                    $safeUrl = e($url);
                    $attachHtml .= '<a href="' . $safeUrl . '" target="_blank"><img src="' . $safeUrl . '" style="max-width:140px;max-height:110px;border-radius:6px;border:1px solid rgba(0,0,0,.1);object-fit:cover;"></a>';
                }
                $attachHtml .= '</div>';
            }

            $html .= '<div style="padding:12px 14px;border-radius:8px;background:' . $bg . ';border:1px solid rgba(0,0,0,.06);">';
            $html .= '<div style="display:flex;justify-content:space-between;margin-bottom:6px;">';
            $html .= '<strong style="font-size:12px;font-weight:700;color:' . $color . ';">' . $senderLabel . '</strong>';
            $html .= '<span style="font-size:11px;color:#9ca3af;">' . $time . '</span>';
            $html .= '</div>';
            $html .= $msgText . $attachHtml;
            $html .= '</div>';
        }

        if (!$record->messages->count()) {
            $html .= '<p style="color:#9ca3af;font-size:13px;">No messages yet.</p>';
        }

        $html .= '</div>';
        return $html;
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                TextColumn::make('ticket_number')
                    ->label('#')
                    ->sortable()
                    ->searchable()
                    ->weight('bold')
                    ->color('primary'),

                TextColumn::make('subject')
                    ->label('Subject')
                    ->searchable()
                    ->limit(55),

                TextColumn::make('customer_name')
                    ->label('Customer')
                    ->searchable()
                    ->default('—'),

                TextColumn::make('category')
                    ->label('Category')
                    ->badge()
                    ->color(fn(string $state): string => match($state) {
                        'billing'   => 'warning',
                        'technical' => 'info',
                        'general'   => 'gray',
                        default     => 'gray',
                    }),

                TextColumn::make('status')
                    ->label('Status')
                    ->badge()
                    ->color(fn(string $state): string => match($state) {
                        'need_human'  => 'danger',
                        'open'        => 'warning',
                        'ai_answered' => 'info',
                        'replied'     => 'success',
                        'closed'      => 'gray',
                        default       => 'gray',
                    })
                    ->formatStateUsing(fn(string $state): string => match($state) {
                        'need_human'  => '⚠ Need Human',
                        'open'        => 'Open',
                        'ai_answered' => 'AI Answered',
                        'replied'     => 'Replied',
                        'closed'      => 'Closed',
                        default       => ucfirst($state),
                    }),

                TextColumn::make('created_at')
                    ->label('Created')
                    ->dateTime('d M Y, H:i')
                    ->sortable(),
            ])
            ->defaultSort('created_at', 'desc')
            ->striped()
            ->actions([
                Action::make('view_reply')
                    ->label('View & Reply')
                    ->icon('heroicon-o-chat-bubble-left-right')
                    ->color('primary')
                    ->modalHeading(fn(Ticket $record): string => $record->ticket_number . ' — ' . $record->subject)
                    ->modalWidth('2xl')
                    ->form(function (Ticket $record): array {
                        $threadHtml = self::buildThreadHtml($record);
                        $aiDraft    = self::getAiDraft($record);

                        $fields = [
                            Placeholder::make('conversation')
                                ->label('Conversation')
                                ->content(new HtmlString($threadHtml)),
                        ];

                        if ($aiDraft) {
                            $fields[] = Textarea::make('ai_draft')
                                ->label('🤖 AI Suggested Reply')
                                ->default($aiDraft)
                                ->disabled()
                                ->rows(5)
                                ->extraAttributes(['style' => 'font-family:monospace;font-size:12px;background:#f0f9ff;border:1px solid #bae6fd;color:#0369a1;']);
                        }

                        $fields[] = Select::make('new_status')
                            ->label('Change Status')
                            ->options([
                                'open'        => 'Open',
                                'ai_answered' => 'AI Answered',
                                'need_human'  => 'Need Human',
                                'replied'     => 'Replied',
                                'closed'      => 'Closed',
                            ])
                            ->default($record->status);

                        $fields[] = Textarea::make('reply_message')
                            ->label('Your Reply')
                            ->placeholder('Type your reply to the customer…')
                            ->rows(4);

                        $fields[] = FileUpload::make('attachment_files')
                            ->label('Attach Images (optional)')
                            ->image()
                            ->multiple()
                            ->disk('public')
                            ->directory('ticket-attachments')
                            ->acceptedFileTypes(['image/jpeg', 'image/png', 'image/webp', 'image/gif'])
                            ->maxSize(10240)
                            ->reorderable(false)
                            ->panelLayout('grid')
                            ->maxFiles(5);

                        return $fields;
                    })
                    ->action(function (Ticket $record, array $data): void {
                        $status  = $data['new_status'] ?? $record->status;
                        $reply   = trim($data['reply_message'] ?? '');
                        $paths   = $data['attachment_files'] ?? [];
                        if (!is_array($paths)) $paths = $paths ? [$paths] : [];

                        $attachUrls = array_values(array_filter(array_map(function($path) {
                            return 'https://www.bazar.uk/storage/' . $path;
                        }, $paths)));

                        $record->status = $status;
                        $record->save();

                        if ($reply || $attachUrls) {
                            TicketMessage::create([
                                'ticket_id'   => $record->id,
                                'sender_type' => 'human',
                                'message'     => $reply ?: '',
                                'attachments' => $attachUrls ?: null,
                            ]);
                            if (!in_array($status, ['closed'])) {
                                $record->status = 'replied';
                                $record->client_unread = ($record->client_unread ?? 0) + 1;
                                $record->save();
                            }
                        }

                        Notification::make()
                            ->title('Ticket updated successfully')
                            ->success()
                            ->send();
                    })
                    ->modalSubmitActionLabel('Save & Send Reply'),
            ])
            ->bulkActions([
                BulkActionGroup::make([
                    DeleteBulkAction::make(),
                ]),
            ]);
    }

    public static function getPages(): array
    {
        return [
            'index' => \App\Filament\Resources\TicketResource\Pages\ListTickets::route('/'),
        ];
    }
}
