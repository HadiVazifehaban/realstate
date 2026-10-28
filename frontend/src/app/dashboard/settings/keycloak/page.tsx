import { KeycloakAdminPanel } from '@/features/keycloak-admin/components/keycloak-admin-panel';

export const metadata = { title: 'مدیریت Keycloak' };

export default function KeycloakAdminPage() {
  return <KeycloakAdminPanel resource="dashboard" />;
}