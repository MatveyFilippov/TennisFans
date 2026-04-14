import { apiClient } from './client.js';
export const matchesApi = {
    async getAll(playerId, playedAfter, playedBefore) {
        const params = new URLSearchParams();
        if (playerId)
            params.append('player_id', playerId.toString());
        if (playedAfter)
            params.append('played_after', playedAfter);
        if (playedBefore)
            params.append('played_before', playedBefore);
        const query = params.toString();
        return apiClient.get(`/matches?${query}`);
    },
    async getById(matchId) {
        return apiClient.get(`/matches/${matchId}`);
    },
    async register(data) {
        return apiClient.post('/matches', data);
    },
    async delete(matchId) {
        return apiClient.delete(`/matches/${matchId}`);
    },
};
