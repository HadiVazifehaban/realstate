# 组件树 - 互代理协作模块

## 現有コンポーネント構造 (変更なしまたは拡張)
src/components/
├── ui/                    # shadcn/uiコンポーネント (変更なし)
├── layout/                # レイアウトコンポーネント
│   ├── app-sidebar.tsx    # 拡張: 新しいネットワークグループ項目を追加するためにuseFilteredNavGroupsフックを修正する必要があるかもしれませんが、構造は変更しません
│   ├── header.tsx
│   ├── user-nav.tsx
│   ├── providers.tsx
│   ├── page-container.tsx
│   └── ... (その他)
├── forms/                 # フォームコンポーネント
├── themes/                # テーマシステム
├── kbar/                  # Command+K検索バー
├── icons.tsx              # アイコンレジストリ (新しいアイコンを追加する必要がある)
└── features/              # フィーチャーベースのコンポーネント
    ├── workspaces/        # 拡張
    │   ├── components/
    │   │   ├── office-page.tsx               # 拡張: 新しいサブアイテムへのリンクを追加
    │   │   ├── clerk-workspace-widgets.tsx
    │   │   └── ... (その他)
    │   └── ... (その他)
    ├── users/             # 拡張
    │   └── components/
    │       ├── user-listing.tsx              # 拡張: 間オフィス役割と権限を表示するために変更
    │       ├── role-breakdown.tsx
    │       ├── user-form-sheet.tsx
    │       └── users-table/
    │           └── columns.tsx               # 拡張: 間オフィス役割列を追加
    ├── properties/        # 拡張
    │   └── components/
    │       ├── property-detail-page.tsx      # 拡張: 共有/転送/紹介アクションボタンを追加
    │       ├── listing-card.tsx              # 拡張: 共有状態バッジを追加
    │       ├── property-media-uploader.tsx
    │       ├── hero-gallery.tsx
    │       ├── bargain-radar-page.tsx
    │       ├── submit-property-page.tsx
    │       ├── visit-scheduler-widget.tsx    # 注意: visit_dateはオブジェクトスキーマに追加しない
    │       └── ... (その他)
    │           # 新しいモーダルコンポーネント:
    │           ├── share-listing-modal.tsx   # 新規
    │           ├── transfer-listing-modal.tsx # 新規
    │           ├── referral-modal.tsx        # 新規
    │           └── permission-settings-modal.tsx # 新規
    ├── crm/               # 拡張
    │   └── components/
    │       ├── crm-board-page.tsx            # 拡張: 共同取引タブを追加
    │       ├── co-broke-deals/               # 新規ディレクトリ
    │       │   ├── co-broke-deals-page.tsx   # 新規
    │       │   ├── co-broke-deal-detail.tsx  # 新規
    │       │   ├── collaboration-partners.tsx # 新規
    │       │   ├── commission-splits.tsx     # 新規
    │       │   ├── deal-events.tsx           # 新規
    │       │   ├── deal-payments.tsx         # 新規
    │       │   ├── deal-disputes.tsx         # 新規
    │       │   └── deal-documents.tsx        # 新規
    │       ├── lead-card.tsx
    │       ├── lead-detail-drawer.tsx
    │       ├── new-lead-dialog.tsx
    │       └── ... (その他)
    └── network/           # 新規ディレクトリ - 間オフィス協力モジュールのメインコンポーネント
        ├── components/
        │   # 共通コンポーネント
        │   ├── agency-card.tsx                 # 新規: 事務所カード
        │   ├── cooperation-status-badge.tsx    # 新規: 協力状態バッジ
        │   ├── permission-matrix.tsx           # 新規: 権限マトリックス
        │   ├── commission-split-editor.tsx     # 新規: コミッション割り振りエディター
        │   ├── audit-event-list.tsx            # 新規: 監査イベントリスト
        │   ├── dispute-timeline.tsx            # 新規: 争議タイムライン
        │   ├── secure-reveal-field.tsx         # 新規: セキュア開示フィールド (電話番号、住所など)
        │   ├── expiry-indicator-badge.tsx      # 新規: 有効期限インдиケーターバッジ
        │   ├── cross-office-access-badge.tsx   # 新規: 間オフィスアクセスバッジ
        │   └── ... (その他の共有コンポーネント)
        #
        # 事務所関連
        │   ├── agencies/
        │   │   ├── agency-list.tsx             # 新規: 事務所リスト
        │   │   ├── agency-grid.tsx             # 新規: 事務所グリッド
        │   │   ├── agency-filter-bar.tsx       # 新規: 事務所フィルターバー
        │   │   ├── agency-sort-options.tsx     # 新規: 事務所ソートオプション
        │   │   └── agency-details.tsx          # 新規: 事務所詳細
        │   #
        # 協力リクエスト関連
        │   ├── requests/
        │   │   ├── cooperation-request-list.tsx # 新規: 協力リクエストリスト
        │   │   ├── cooperation-request-card.tsx # 新規: 協力リクエストカード
        │   │   ├── cooperation-request-details.tsx # 新規: 協力リクエスト詳細
        │   │   ├── request-actions.tsx         # 新規: リクエストアクション (承認/拒否など)
        │   │   └── request-form.tsx            # 新規: 協力リクエストフォーム
        │   #
        # 共有物件関連
        │   ├── shared-listings/
        │   │   ├── shared-listing-list.tsx     # 新規: 共有物件リスト
        │   │   ├── shared-listing-card.tsx     # 新規: 共有物件カード
        │   │   ├── shared-listing-details.tsx  # 新規: 共有物件詳細
        │   │   ├── permission-badge.tsx        # 新規: 権限バッジ
        │   │   ├── share-actions.tsx           # 新規: 共有アクション
        │   │   └── shared-listing-form.tsx     # 新規: 共有物件フォーム
        │   #
        # 紹介関連
        │   ├── referrals/
        │   │   ├── referral-list.tsx           # 新規: 紹介リスト
        │   │   ├── referral-card.tsx           # 新規: 紹介カード
        │   │   ├── referral-details.tsx        # 新規: 紹介詳細
        │   │   └── referral-form.tsx           # 新規: 紹介フォーム
        │   #
        # ファイル転送関連
        │   ├── transfers/
        │   │   ├── transfer-list.tsx           # 新規: ファイル転送リスト
        │   │   ├── transfer-card.tsx           # 新規: ファイル転送カード
        │   │   ├── transfer-details.tsx        # 新規: ファイル転送詳細
        │   │   └── transfer-form.tsx           # 新規: ファイル転送フォーム
        │   #
        # コミッション関連
        │   ├── commissions/
        │   │   ├── commission-ledger.tsx       # 新規: コミッション台帳
        │   │   ├── commission-ledger-table.tsx # 新規: コミッション台帳テーブル
        │   │   ├── commission-details.tsx      # 新規: コミッション詳細
        │   │   ├── payment-history.tsx         # 新規: 支払い履歴
        │   │   ├── dispute-timeline.tsx        # 新規: 争議タイムライン (上記参照)
        │   │   └── commission-form.tsx         # 新規: コミッションフォーム
        │   #
        # 争議関連
        │   ├── disputes/
        │   │   ├── dispute-list.tsx            # 新規: 争議リスト
        │   │   ├── dispute-card.tsx            # 新規: 争議カード
        │   │   ├── dispute-details.tsx         # 新規: 争議詳細
        │   │   ├── dispute-timeline.tsx        # 新規: 争議タイムライン (上記参照)
        │   │   ├── dispute-form.tsx            # 新規: 争議フォーム
        │   │   └── dispute-resolution.tsx      # 新規: 争議解決
        │   #
        # レポート関連
        │   ├── reports/
        │   │   ├── collaboration-report.tsx    # 新規: 協力レポート
        │   │   ├── report-filters.tsx          # 新規: レポートフィルター
        │   │   └── report-charts.tsx           # 新規: レポートチャート
        │   #
        # 監査関連
        │   ├── audit/
        │   │   ├── audit-event-list.tsx        # 新規: 監査イベントリスト (上記参照)
        │   │   ├── audit-event-details.tsx     # 新規: 監査イベント詳細
        │   │   └── audit-filters.tsx           # 新規: 監査フィルター
        │   #
        # ページコンポーネント
        │   └── pages/
        │       ├── agencies-page.tsx           # 新規: 事務所ページ
        │       ├── requests-page.tsx           # 新規: 協力リクエストページ
        │       ├── shared-listings-page.tsx    # 新規: 共有物件ページ
        │       ├── referrals-page.tsx          # 新規: 紹介ページ
        │       ├── transfers-page.tsx          # 新規: ファイル転送ページ
        │       ├── commissions-page.tsx        # 新規: コミッションページ
        │       ├── disputes-page.tsx           # 新規: 争議ページ
        │       ├── reports-page.tsx            # 新規: レポートページ
        │       └── audit-page.tsx              # 新規: 監査ページ

## アイコンレジストリの更新
src/components/icons.tsx に新しいアイコンを追加する必要があります:
- handshake (協力)
- office-building (事務所)
- shield-check (セキュア共有)
- split (コミッション割り振り)
- gavel (争議)
- audit (監査)
- referral (紹介)
- transfer (転送)
- network (ネットワーク)
- clipper-list (権限マトリックス)

## デザインシステムコンポーネント
新しいコンポーネントは以下の既存のデザインパターンに従う必要があります:
- shadcn/uiプリミティブを使用 (カード、ボタン、バッジなど)
- cn() ユーティリティでクラス名をマージ
- TypeScriptで厳密な型付け
- サーバーコンポーネントを優先し、クライアントコンポーネントは必要に応じてのみ使用
- RTLレイアウトをサポート
- 既存のエラーハンドリングとローディング状態パターンに従う
- 既存の成功/エラートーストパターンに従う