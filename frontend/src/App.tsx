import { Suspense, lazy } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import PageSkeleton from './components/PageSkeleton';
import Protected from './components/Protected';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const RegisterPage = lazy(() => import('./pages/RegisterPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const CampaignsPage = lazy(() => import('./pages/CampaignsPage'));
const CampaignDetailPage = lazy(() => import('./pages/CampaignDetailPage'));
const ContentPage = lazy(() => import('./pages/ContentPage'));
const CalendarPage = lazy(() => import('./pages/CalendarPage'));
const ResultsPage = lazy(() => import('./pages/ResultsPage'));
const SuggestionsPage = lazy(() => import('./pages/SuggestionsPage'));
const ProductsPage = lazy(() => import('./pages/ProductsPage'));
const OrdersPage = lazy(() => import('./pages/OrdersPage'));
const ChannelsPage = lazy(() => import('./pages/ChannelsPage'));
const GrowthPage = lazy(() => import('./pages/GrowthPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageSkeleton />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<Protected />}>
            <Route index element={<DashboardPage />} />
            <Route path="campaigns" element={<CampaignsPage />} />
            <Route path="campaigns/:id" element={<CampaignDetailPage />} />
            <Route path="content" element={<ContentPage />} />
            <Route path="calendar" element={<CalendarPage />} />
            <Route path="results" element={<ResultsPage />} />
            <Route path="suggestions" element={<SuggestionsPage />} />
            <Route path="products" element={<ProductsPage />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="channels" element={<ChannelsPage />} />
            <Route path="growth" element={<GrowthPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
