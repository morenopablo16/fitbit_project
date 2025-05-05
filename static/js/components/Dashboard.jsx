import React, { useState, useEffect } from 'react';
import { 
    Container, 
    Grid, 
    Paper, 
    Typography, 
    Box,
    Card,
    CardContent,
    IconButton,
    LinearProgress,
    Alert,
    Snackbar
} from '@mui/material';
import {
    DirectionsWalk as StepsIcon,
    Favorite as HeartIcon,
    Hotel as SleepIcon,
    AccessTime as SedentaryIcon,
    Notifications as AlertIcon
} from '@mui/icons-material';

const Dashboard = () => {
    const [data, setData] = useState({
        dailySummary: null,
        alerts: [],
        loading: true,
        error: null
    });

    useEffect(() => {
        fetchDashboardData();
    }, []);

    const fetchDashboardData = async () => {
        try {
            const [summaryResponse, alertsResponse] = await Promise.all([
                fetch('/api/daily_summary'),
                fetch('/api/alerts')
            ]);

            const summaryData = await summaryResponse.json();
            const alertsData = await alertsResponse.json();

            setData({
                dailySummary: summaryData,
                alerts: alertsData,
                loading: false,
                error: null
            });
        } catch (error) {
            setData(prev => ({
                ...prev,
                loading: false,
                error: 'Error al cargar los datos del dashboard'
            }));
        }
    };

    const MetricCard = ({ title, value, icon, unit, color }) => (
        <Card sx={{ height: '100%' }}>
            <CardContent>
                <Box display="flex" alignItems="center" mb={2}>
                    {React.createElement(icon, { style: { color, fontSize: 30 } })}
                    <Typography variant="h6" ml={1} color="textSecondary">
                        {title}
                    </Typography>
                </Box>
                <Typography variant="h4" component="div">
                    {value !== null ? value.toLocaleString() : '-'} {unit}
                </Typography>
            </CardContent>
        </Card>
    );

    if (data.loading) {
        return (
            <Container>
                <Box mt={4}>
                    <LinearProgress />
                </Box>
            </Container>
        );
    }

    return (
        <Container>
            <Box mt={4} mb={4}>
                <Typography variant="h4" gutterBottom>
                    Dashboard de Actividad
                </Typography>

                <Grid container spacing={3}>
                    {/* Métricas principales */}
                    <Grid item xs={12} sm={6} md={3}>
                        <MetricCard
                            title="Pasos"
                            value={data.dailySummary?.steps}
                            icon={StepsIcon}
                            unit="pasos"
                            color="#2196f3"
                        />
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                        <MetricCard
                            title="Ritmo Cardíaco"
                            value={data.dailySummary?.heart_rate}
                            icon={HeartIcon}
                            unit="bpm"
                            color="#f44336"
                        />
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                        <MetricCard
                            title="Sueño"
                            value={data.dailySummary?.sleep_minutes && 
                                   Math.round(data.dailySummary.sleep_minutes / 60)}
                            icon={SleepIcon}
                            unit="horas"
                            color="#9c27b0"
                        />
                    </Grid>
                    <Grid item xs={12} sm={6} md={3}>
                        <MetricCard
                            title="Tiempo Sedentario"
                            value={data.dailySummary?.sedentary_minutes && 
                                   Math.round(data.dailySummary.sedentary_minutes / 60)}
                            icon={SedentaryIcon}
                            unit="horas"
                            color="#ff9800"
                        />
                    </Grid>

                    {/* Alertas */}
                    <Grid item xs={12}>
                        <Paper sx={{ p: 2 }}>
                            <Box display="flex" alignItems="center" mb={2}>
                                <AlertIcon color="warning" sx={{ mr: 1 }} />
                                <Typography variant="h6">
                                    Alertas Recientes
                                </Typography>
                            </Box>
                            {data.alerts.length > 0 ? (
                                data.alerts.map((alert, index) => (
                                    <Alert 
                                        key={index}
                                        severity={alert.priority === 'high' ? 'error' : 
                                                 alert.priority === 'medium' ? 'warning' : 'info'}
                                        sx={{ mb: 1 }}
                                    >
                                        {alert.details}
                                    </Alert>
                                ))
                            ) : (
                                <Typography color="textSecondary">
                                    No hay alertas recientes
                                </Typography>
                            )}
                        </Paper>
                    </Grid>
                </Grid>
            </Box>

            {/* Snackbar para errores */}
            <Snackbar 
                open={!!data.error} 
                autoHideDuration={6000} 
                onClose={() => setData(prev => ({ ...prev, error: null }))}
            >
                <Alert severity="error" onClose={() => setData(prev => ({ ...prev, error: null }))}>
                    {data.error}
                </Alert>
            </Snackbar>
        </Container>
    );
};

export default Dashboard; 