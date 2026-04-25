<x-filament-panels::page>

    @if($flash)
        <div style="margin-bottom:16px;padding:12px 16px;border-radius:8px;font-size:14px;font-weight:500;
                    background:{{ $flashType === 'success' ? '#dcfce7' : '#fee2e2' }};
                    color:{{ $flashType === 'success' ? '#166534' : '#991b1b' }};
                    border:1px solid {{ $flashType === 'success' ? '#86efac' : '#fca5a5' }}">
            {{ $flash }}
        </div>
    @endif

    <div style="margin-bottom:16px;display:flex;align-items:center;justify-content:space-between">
        <div style="font-size:14px;color:#6b7280">
            Pending review: <strong style="color:#111827">{{ $pendingCount }}</strong>
        </div>
        <button wire:click="loadQueue"
                style="font-size:13px;padding:6px 14px;border-radius:8px;border:1px solid #d1d5db;background:#fff;cursor:pointer;display:flex;align-items:center;gap:6px">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
            Refresh
        </button>
    </div>

    @if(empty($items))
        <div style="text-align:center;padding:48px 24px;color:#9ca3af;font-size:15px">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#d1d5db" stroke-width="1.5" style="margin:0 auto 12px;display:block">
                <path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
            </svg>
            No items in the moderation queue
        </div>
    @else
        <div style="overflow-x:auto">
            <table style="width:100%;border-collapse:collapse;font-size:13px">
                <thead>
                    <tr style="background:#f9fafb;border-bottom:2px solid #e5e7eb">
                        <th style="padding:10px 12px;text-align:left;font-weight:600;color:#374151">ID</th>
                        <th style="padding:10px 12px;text-align:left;font-weight:600;color:#374151">Ad</th>
                        <th style="padding:10px 12px;text-align:left;font-weight:600;color:#374151">AI flags</th>
                        <th style="padding:10px 12px;text-align:left;font-weight:600;color:#374151">Confidence</th>
                        <th style="padding:10px 12px;text-align:left;font-weight:600;color:#374151">Status</th>
                        <th style="padding:10px 12px;text-align:left;font-weight:600;color:#374151">Date</th>
                        <th style="padding:10px 12px;text-align:left;font-weight:600;color:#374151">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    @foreach($items as $item)
                        <tr style="border-bottom:1px solid #f3f4f6;{{ $item['status'] === 'pending' ? 'background:#fffbeb' : '' }}">

                            {{-- ID + link --}}
                            <td style="padding:10px 12px;color:#6b7280;white-space:nowrap;vertical-align:top">
                                {{ $item['id'] }}
                                @if($item['property_id'])
                                    <br><a href="https://www.bazar.uk/{{ $item['property_id'] }}"
                                           target="_blank"
                                           style="color:#f97316;font-size:11px">
                                        Ad #{{ $item['property_id'] }} ↗
                                    </a>
                                @endif
                            </td>

                            {{-- Title + description --}}
                            <td style="padding:10px 12px;max-width:240px;vertical-align:top">
                                <div style="font-weight:600;color:#111827;margin-bottom:3px">
                                    {{ Str::limit($item['title'], 60) }}
                                </div>
                                <div style="color:#6b7280;font-size:12px;line-height:1.4">
                                    {{ Str::limit($item['description'], 100) }}
                                </div>
                            </td>

                            {{-- AI flags (text + image) --}}
                            <td style="padding:10px 12px;max-width:220px;vertical-align:top">

                                @if(!empty($item['ai_text_flagged']) && !empty($item['ai_reasons']))
                                    <div style="margin-bottom:5px">
                                        <span style="font-size:10px;font-weight:700;color:#92400e;text-transform:uppercase;letter-spacing:.5px">
                                            📝 Text
                                        </span><br>
                                        @foreach($item['ai_reasons'] as $reason)
                                            <span style="display:inline-block;background:#fef3c7;color:#92400e;border:1px solid #fcd34d;border-radius:4px;padding:2px 7px;font-size:11px;margin:2px 2px 2px 0">
                                                {{ $reason }}
                                            </span>
                                        @endforeach
                                    </div>
                                @endif

                                @if(!empty($item['ai_image_flagged']) && !empty($item['ai_image_reasons']))
                                    <div>
                                        <span style="font-size:10px;font-weight:700;color:#991b1b;text-transform:uppercase;letter-spacing:.5px">
                                            🖼 Image
                                        </span><br>
                                        @foreach($item['ai_image_reasons'] as $reason)
                                            <span style="display:inline-block;background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;border-radius:4px;padding:2px 7px;font-size:11px;margin:2px 2px 2px 0">
                                                {{ $reason }}
                                            </span>
                                        @endforeach
                                    </div>
                                @endif

                                @if(empty($item['ai_text_flagged']) && empty($item['ai_image_flagged']))
                                    <span style="color:#9ca3af;font-size:12px">—</span>
                                @endif
                            </td>

                            {{-- Confidence bar --}}
                            <td style="padding:10px 12px;white-space:nowrap;vertical-align:top">
                                @php $conf = round(($item['ai_confidence'] ?? 0) * 100); @endphp
                                <div style="display:flex;align-items:center;gap:6px">
                                    <div style="width:48px;height:6px;border-radius:3px;background:#e5e7eb;overflow:hidden">
                                        <div style="height:100%;width:{{ $conf }}%;background:{{ $conf > 70 ? '#ef4444' : ($conf > 40 ? '#f97316' : '#22c55e') }};border-radius:3px"></div>
                                    </div>
                                    <span style="color:#374151">{{ $conf }}%</span>
                                </div>
                                {{-- Source badges --}}
                                <div style="margin-top:4px;display:flex;gap:4px">
                                    @if(!empty($item['ai_text_flagged']))
                                        <span title="Flagged by Gemini text moderation"
                                              style="font-size:10px;background:#e0e7ff;color:#3730a3;border-radius:4px;padding:1px 5px">Gemini</span>
                                    @endif
                                    @if(!empty($item['ai_image_flagged']))
                                        <span title="Flagged by Google Vision SafeSearch"
                                              style="font-size:10px;background:#fce7f3;color:#9d174d;border-radius:4px;padding:1px 5px">Vision</span>
                                    @endif
                                </div>
                            </td>

                            {{-- Status badge --}}
                            <td style="padding:10px 12px;white-space:nowrap;vertical-align:top">
                                @if($item['status'] === 'pending')
                                    <span style="background:#fef3c7;color:#92400e;border:1px solid #fcd34d;border-radius:12px;padding:3px 10px;font-size:12px;font-weight:600">
                                        Pending
                                    </span>
                                @elseif($item['status'] === 'approved')
                                    <span style="background:#dcfce7;color:#166534;border:1px solid #86efac;border-radius:12px;padding:3px 10px;font-size:12px;font-weight:600">
                                        Approved
                                    </span>
                                @else
                                    <span style="background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;border-radius:12px;padding:3px 10px;font-size:12px;font-weight:600">
                                        Rejected
                                    </span>
                                @endif
                            </td>

                            {{-- Date --}}
                            <td style="padding:10px 12px;color:#6b7280;white-space:nowrap;font-size:12px;vertical-align:top">
                                {{ date('d M Y', (int)$item['created_at']) }}<br>
                                <span style="color:#9ca3af">{{ date('H:i', (int)$item['created_at']) }}</span>
                            </td>

                            {{-- Actions --}}
                            <td style="padding:10px 12px;white-space:nowrap;vertical-align:top">
                                @if($item['status'] === 'pending')
                                    <div style="display:flex;flex-direction:column;gap:6px">
                                        <button wire:click="approve({{ $item['id'] }})"
                                                style="background:#16a34a;color:#fff;border:none;border-radius:7px;padding:7px 14px;font-size:12px;font-weight:600;cursor:pointer">
                                            ✓ Approve
                                        </button>
                                        <button wire:click="reject({{ $item['id'] }})"
                                                onclick="return confirm('Reject this listing?')"
                                                style="background:#dc2626;color:#fff;border:none;border-radius:7px;padding:7px 14px;font-size:12px;font-weight:600;cursor:pointer">
                                            ✕ Reject
                                        </button>
                                    </div>
                                @else
                                    <span style="color:#9ca3af;font-size:11px">
                                        {{ date('d M H:i', (int)$item['reviewed_at']) }}
                                    </span>
                                @endif
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        </div>
    @endif

</x-filament-panels::page>
