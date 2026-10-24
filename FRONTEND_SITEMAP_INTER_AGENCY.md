# 前端站点地图 - 互代理协作模块

## 现有结构保持不变
- /dashboard/overview → ダッシュボード
- /dashboard/properties → ラスパーサーチレーダー (価格ハンティングレーダー)
- /dashboard/properties/submit → 物件登録
- /dashboard/crm → 取引デスク
- /dashboard/avm → 市場分析とAVM
- /dashboard/workspaces → マイオフィス
- /dashboard/workspaces/team → チーム
- /dashboard/product → 製品
- /dashboard/users → ユーザー
- /dashboard/chat → チャット
- /dashboard/ai-chat → AIチャット
- /dashboard/events → CRMイベント
- /dashboard/pipeline → 5段階パイプライン
- /dashboard/streams → ジョブキュー
- /dashboard/pii → PII vault
- /dashboard/audit → 監査ログ
- /dashboard/profile → プロフィール
- /dashboard/notifications → 通知
- /dashboard/billing → 請求書
- /dashboard/exclusive → 特別セクション

## 新增路由 - 互代理协作模块

### 新增顶级导航项
- /dashboard/network → ネットワーク協力事務所 (新規トップレベルグループ)

### マイオフィス拡張 (現構造保持、サブアイテム追加)
- /dashboard/workspaces → マイオフィス (メイン)
- /dashboard/workspaces/profile → オフィスプロフィール (新規)
- /dashboard/workspaces/branches → 支店と連絡先情報 (新規)
- /dashboard/workspaces/collaboration-settings → 間オフィス協力設定 (新規)
- /dashboard/workspaces/agreements → 契約と了解覚書 (新規)
- /dashboard/workspaces/default-commission → デフォルトコミッション設定 (新規)
- /dashboard/workspaces/external-access → 外部オフィスアクセスレベル (新規)
- /dashboard/workspaces/collaboration-history → 協力履歴 (新規)

### チーム拡張 (現構造保持、サブアイテム追加)
- /dashboard/workspaces/team → チーム (メイン)
- /dashboard/workspaces/team/roles → 間オフィス役割 (新規)
- /dashboard/workspaces/team/permissions → 協力権限 (新規)
- /dashboard/workspaces/team/file-sharing-members → ファイル共有承認メンバー (新規)
- /dashboard/workspaces/team/negotiation-members → 交渉/見学/クローズ承認メンバー (新規)
- /dashboard/workspaces/team/client-info-restrictions → 所有者/顧客情報表示制限 (新規)

### 物件登録拡張 (アクションポイント追加、ルート変更なし)
- /dashboard/properties/submit → 物件登録 (メイン)
  - アクション: 同僚オフィスと共有 (新規モーダル)
  - アクション: 関連顧客/リードを紹介 (新規モーダル)
  - アクション: ファイル転送 (新規モーダル)
  - アクション: アクセスレベル設定 (新規モーダル)
  - アクション: 共有有効期限設定 (新規モーダル)
  - アクション: ファイル別コミッション設定 (新規モーダル)

### 取引デスク拡張 (現構造保持、タブ/パネル追加)
- /dashboard/crm → 取引デスク (メイン)
  - タブ: 共同取引 (新規)
    - サブタブ: 協力パートナー
    - サブタブ: コミッション割り振り
    - サブタブ: イベント
    - サブタブ: 支払い
    - サブタブ: 争議
    - サブタブ: ドキュメント

### ネットワーク協力事務所 (新規トップレベルグループ)
- /dashboard/network/agencies → 協力事務所 (新規)
- /dashboard/network/requests → 協力リクエスト (新規)
  - タブ: 受信
  - タブ: 送信
  - タブ: 保留中
  - タブ: 承認済み
  - タブ: 拒否済み
  - タブ: 期限切れ
- /dashboard/network/shared-listings → 共有物件 (新規)
  - タブ: 送信済み
  - タブ: 受信済み
  - タブ: 期限切れ
  - タブ: 取り消し済み
  - タブ: 行動必要
- /dashboard/network/referrals → 紹介 (新規)
- /dashboard/network/transfers → ファイル転送 (新規)
- /dashboard/network/commissions → コミッションと決済 (新規)
- /dashboard/network/disputes → 争議 (新規)
- /dashboard/network/reports → 協力レポート (新規)
- /dashboard/network/audit → 追跡とログ (新規)

## 特別注意事項
1. すべての新しいルートはペルシャ語RTLレイアウトを維持する必要があります
2. 新しいルートは既存のレイアウトシェル（ヘッダー、サイドバーなど）を使用しなければなりません
3. ルートの命名規則は既存のパターンに従う必要があります（ケバブケース、ペルシャ語ラベル）
4. 新しいルートは同じ認証と組織チェックを適用する必要があります