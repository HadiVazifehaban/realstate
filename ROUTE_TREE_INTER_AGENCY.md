# 路由树 - 互代理协作模块

## 現有ルート構造 (変更なし)
src/app/
├── layout.tsx
├── page.tsx
├── global-error.tsx
└── not-found.tsx
├── auth/
│   └── ... (サインイン/サインアップ)
└── dashboard/
    ├── layout.tsx
    ├── page.tsx
    ├── overview/
    │   └── page.tsx
    ├── properties/                    # 不変更
    │   ├── layout.tsx
    │   ├── page.tsx                   # ラスパーサーチレーダー
    │   ├── submit/
    │   │   └── page.tsx               # 物件登録
    │   └── [id]/
    │       └── page.tsx               # 物件詳細
    ├── crm/                           # 不変更
    │   ├── layout.tsx
    │   └── page.tsx                   # CRMボード
    ├── avm/
    │   └── page.tsx                   # 市場分析とAVM
    ├── workspaces/                    # 拡張
    │   ├── layout.tsx
    │   ├── page.tsx                   # マイオフィス (メイン)
    │   ├── profile/                   # 新規
    │   │   └── page.tsx               # オフィスプロフィール
    │   ├── branches/                  # 新規
    │   │   └── page.tsx               # 支店と連絡先情報
    │   ├── collaboration-settings/    # 新規
    │   │   └── page.tsx               # 間オフィス協力設定
    │   ├── agreements/                # 新規
    │   │   └── page.tsx               # 契約と了解覚書
    │   ├── default-commission/        # 新規
    │   │   └── page.tsx               # デフォルトコミッション設定
    │   ├── external-access/           # 新規
    │   │   └── page.tsx               # 外部オフィスアクセスレベル
    │   ├── collaboration-history/     # 新規
    │   │   └── page.tsx               # 協力履歴
    │   └── team/                      # 拡張
    │       ├── layout.tsx
    │       ├── page.tsx               # チーム (メイン)
    │       ├── roles/                 # 新規
    │       │   └── page.tsx           # 間オフィス役割
    │       ├── permissions/           # 新規
    │       │   └── page.tsx           # 協力権限
    │       ├── file-sharing-members/  # 新規
    │       │   └── page.tsx           # ファイル共有承認メンバー
    │       ├── negotiation-members/   # 新規
    │       │   └── page.tsx           # 交渉/見学/クローズ承認メンバー
    │       └── client-info-restrictions/ # 新規
    │           └── page.tsx           # 所有者/顧客情報表示制限
    ├── product/
    │   └── page.tsx
    ├── users/
    │   └── page.tsx
    ├── chat/
    │   └── page.tsx
    ├── ai-chat/
    │   └── page.tsx
    └── network/                       # 新規トップレベルグループ
        ├── layout.tsx
        ├── page.tsx                   # ネットワーク協力事務所ダッシュボード
        ├── agencies/                  # 新規
        │   ├── layout.tsx
        │   └── page.tsx               # 協力事務所
        ├── requests/                  # 新規
        │   ├── layout.tsx
        │   ├── page.tsx               # 協力リクエスト (メイン)
        │   ├── incoming/              # 新規
        │   │   └── page.tsx           # 受信リクエスト
        │   ├── sent/                  # 新規
        │   │   └── page.tsx           # 送信リクエスト
        │   ├── pending/               # 新規
        │   │   └── page.tsx           # 保留中リクエスト
        │   ├── accepted/              # 新規
        │   │   └── page.tsx           # 承認済みリクエスト
        │   ├── rejected/              # 新規
        │   │   └── page.tsx           # 拒否済みリクエスト
        │   └── expired/               # 新規
        │       └── page.tsx           # 期限切れリクエスト
        ├── shared-listings/           # 新規
        │   ├── layout.tsx
        │   ├── page.tsx               # 共有物件 (メイン)
        │   ├── sent/                  # 新規
        │   │   └── page.tsx           # 送信済み共有物件
        │   ├── received/              # 新規
        │   │   └── page.tsx           # 受信済み共有物件
        │   ├── expired/               # 新規
        │   │   └── page.tsx           # 期限切れ共有物件
        │   ├── revoked/               # 新規
        │   │   └── page.tsx           # 取り消し済み共有物件
        │   └── action-required/       # 新規
        │       └── page.tsx           # 行動必要共有物件
        ├── referrals/                 # 新規
        │   ├── layout.tsx
        │   └── page.tsx               # 紹介
        ├── transfers/                 # 新規
        │   ├── layout.tsx
        │   └── page.tsx               # ファイル転送
        ├── commissions/               # 新規
        │   ├── layout.tsx
        │   ├── page.tsx               # コミッションと決済 (メイン)
        │   ├── ledger/                # 新規
        │   │   └── page.tsx           # コミッション台帳
        │   ├── payments/              # 新規
        │   │   └── page.tsx           # コミッション支払い
        │   └── agreements/            # 新規
        │       └── page.tsx           # コミッション契約
        ├── disputes/                  # 新規
        │   ├── layout.tsx
        │   ├── page.tsx               # 争議 (メイン)
        │   └── [id]/                  # 新規
        │       └── page.tsx           # 争議詳細
        ├── reports/                   # 新規
        │   ├── layout.tsx
        │   └── page.tsx               # 協力レポート
        └── audit/                     # 新規
            ├── layout.tsx
            └── page.tsx               # 追跡とログ

## CRM拡張 (取引デスク)
src/app/dashboard/crm/
├── layout.tsx
├── page.tsx                           # CRMボード (メイン)
├── co-broke-deals/                    # 新規
│   ├── layout.tsx
│   ├── page.tsx                       # 共同取引 (メイン)
│   └── [dealId]/
│       ├── layout.tsx
│       └── page.tsx                   # 共同取引詳細
│           ├── partners/              # 新規
        │       │   └── page.tsx       # 協力パートナー
        │       ├── splits/            # 新規
        │       │   └── page.tsx       # コミッション割り振り
        │       ├── events/            # 新規
        │       │   └── page.tsx       # イベント
        │       ├── payments/          # 新規
        │       │   └── page.tsx       # 支払い
        │       ├── disputes/          # 新規
        │       │   └── page.tsx       # 争議
        │       └── documents/         # 新規
        │           └── page.tsx       # ドキュメント
└── ... (既存の他のページ)

## 物件詳細ページの拡張 (アクションポイント追加)
src/app/dashboard/properties/[id]/
├── layout.tsx
└── page.tsx                           # 物件詳細 (既存)
    # このページ内に新しいアクションボタン/モーダルを追加:
    # - 同僚オフィスと共有
    # - 関連顧客/リードを紹介
    # - ファイル転送
    # - アクセスレベル設定
    # - 共有有効期限設定
    # - ファイル別コミッション設定