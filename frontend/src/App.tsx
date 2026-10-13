import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import { PermissionGate, ProtectedRoute } from './components/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ProfilePage from './pages/ProfilePage'
import UsersPage from './pages/accounts/UsersPage'
import GroupsPage from './pages/accounts/GroupsPage'
import OrgsPage from './pages/accounts/OrgsPage'
import AppsPage from './pages/authz/AppsPage'
import ToolsPage from './pages/authz/ToolsPage'
import RolesPage from './pages/authz/RolesPage'
import PoliciesPage from './pages/authz/PoliciesPage'
import AuditPage from './pages/audit/AuditPage'
import SecretsPage from './pages/vault/SecretsPage'
import RotationsPage from './pages/vault/RotationsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route
            path="/dashboard"
            element={
              <PermissionGate code="dashboard:read">
                <DashboardPage />
              </PermissionGate>
            }
          />
          <Route
            path="/profile"
            element={
              <PermissionGate code="dashboard:read">
                <ProfilePage />
              </PermissionGate>
            }
          />
          <Route
            path="/accounts/users"
            element={
              <PermissionGate code="user:read">
                <UsersPage />
              </PermissionGate>
            }
          />
          <Route
            path="/accounts/groups"
            element={
              <PermissionGate code="group:read">
                <GroupsPage />
              </PermissionGate>
            }
          />
          <Route
            path="/accounts/orgs"
            element={
              <PermissionGate code="org:read">
                <OrgsPage />
              </PermissionGate>
            }
          />
          <Route
            path="/authz/apps"
            element={
              <PermissionGate code="application:read">
                <AppsPage />
              </PermissionGate>
            }
          />
          <Route
            path="/authz/tools"
            element={
              <PermissionGate code="application:read">
                <ToolsPage />
              </PermissionGate>
            }
          />
          <Route
            path="/authz/roles"
            element={
              <PermissionGate code="role:read">
                <RolesPage />
              </PermissionGate>
            }
          />
          <Route
            path="/authz/policies"
            element={
              <PermissionGate code="policy:read">
                <PoliciesPage />
              </PermissionGate>
            }
          />
          <Route
            path="/audit"
            element={
              <PermissionGate code="audit:read">
                <AuditPage />
              </PermissionGate>
            }
          />
          <Route
            path="/vault/secrets"
            element={
              <PermissionGate code="secret:read">
                <SecretsPage />
              </PermissionGate>
            }
          />
          <Route
            path="/vault/rotations"
            element={
              <PermissionGate code="secret:read">
                <RotationsPage />
              </PermissionGate>
            }
          />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
