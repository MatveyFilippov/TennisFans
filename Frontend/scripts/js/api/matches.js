import { apiClient } from './client.js';
export const matchesApi = {
    async getAllForPlayer(playerId, startDate, endDate) {
        const params = new URLSearchParams();
        params.append('player_id', playerId.toString());
        if (startDate)
            params.append('start_date', startDate);
        if (endDate)
            params.append('end_date', endDate);
        const query = params.toString();
        return apiClient.get(`/matches?${query}`);
    },
    async getById(matchId) {
        return apiClient.get(`/matches/${matchId}`);
    },
    async register(data) {
        return apiClient.post('/matches', data);
    },
};
