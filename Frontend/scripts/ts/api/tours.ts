import { apiClient } from './client.js';
import { TourResponse, CreateTourRequest, EditTourRequest, TourPlayerPointsResponse, TourPlayersPairProposeResponse } from '../types/index.js';

export const toursApi = {
    async getAll(startedAfter?: string, endedBefore?: string): Promise<TourResponse[]> {
        const params = new URLSearchParams();
        if (startedAfter) params.append('started_after', startedAfter);
        if (endedBefore) params.append('ended_before', endedBefore);
        const query = params.toString();
        return apiClient.get<TourResponse[]>(`/tours${query ? `?${query}` : ''}`);
    },

    async getNotEnded(): Promise<TourResponse[]> {
        return apiClient.get<TourResponse[]>('/tours/not_ended');
    },

    async getById(tourId: number): Promise<TourResponse> {
        return apiClient.get<TourResponse>(`/tours/${tourId}`);
    },

    async create(data: CreateTourRequest): Promise<TourResponse> {
        return apiClient.post<TourResponse>('/tours', data);
    },

    async edit(tourId: number, data: EditTourRequest): Promise<TourResponse> {
        return apiClient.patch<TourResponse>(`/tours/${tourId}`, data);
    },
    
    async delete(tourId: number): Promise<void> {
        return apiClient.delete<void>(`/tours/${tourId}`);
    },
    
    async getPlayersPoints(tourId: number): Promise<TourPlayerPointsResponse[]> {
        return apiClient.get<TourPlayerPointsResponse[]>(`/tours/${tourId}/players_points`);
    },

    async getProposedPairs(tourId: number): Promise<TourPlayersPairProposeResponse[]> {
        return apiClient.get<TourPlayersPairProposeResponse[]>(`/tours/${tourId}/propose_players_pairs`);
    },
};
