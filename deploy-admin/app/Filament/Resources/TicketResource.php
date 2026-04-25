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
use Filament\Notifications\Notification;

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
                        $record->load('messages');
                        $threadLines = [];
                        foreach ($record->messages as $msg) {
                            $label = match($msg->sender_type) {
                                'client' => '👤 Customer',
                                'ai'     => '🤖 AI Assistant',
                                'human'  => '✍️ Support Team',
                                default  => $msg->sender_type,
                            };
                            $time = $msg->created_at->format('d M Y H:i');
                            $threadLines[] = "[{$label} — {$time}]\n{$msg->message}";
                        }
                        $threadText = $threadLines
                            ? implode("\n\n" . str_repeat('─', 40) . "\n\n", $threadLines)
                            : 'No messages yet.';

                        $aiDraft = self::getAiDraft($record);

                        $fields = [
                            Textarea::make('thread_preview')
                                ->label('Conversation')
                                ->default($threadText)
                                ->disabled()
                                ->rows(min(count($record->messages) * 4 + 2, 14))
                                ->extraAttributes(['style' => 'font-family:monospace;font-size:12px;background:#f9fafb;']),
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

                        return $fields;
                    })
                    ->action(function (Ticket $record, array $data): void {
                        $status = $data['new_status'] ?? $record->status;
                        $reply  = trim($data['reply_message'] ?? '');

                        $record->status = $status;
                        $record->save();

                        if ($reply) {
                            TicketMessage::create([
                                'ticket_id'   => $record->id,
                                'sender_type' => 'human',
                                'message'     => $reply,
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
