import { KeycloakAdminPanel } from '@/features/keycloak-admin/components/keycloak-admin-panel';

const resources = new Set([
  'users', 'groups', 'roles', 'clients', 'client-scopes', 'realm-settings',
  'authentication', 'identity-providers', 'user-federation', 'events', 'admin-permissions'
]);

export default async function KeycloakResourcePage({ params }: { params: Promise<{ resource: string }> }) {
  const { resource } = await params;
  if (!resources.has(resource)) return <KeycloakAdminPanel resource="not-found" />;
  return <KeycloakAdminPanel resource={resource} />;
}