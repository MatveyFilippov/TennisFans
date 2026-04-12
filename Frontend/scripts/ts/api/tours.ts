import { apiClient } from './client.js';
import { TourResponse, StartTourRequest, EndTourRequest, TourPlayerPointsResponse } from '../types/index.js';

export const toursApi = {
    async getAll(): Promise<TourResponse[]> {
        return apiClient.get<TourResponse[]>('/tours');
    },

    async getNotEnded(): Promise<TourResponse[]> {
        return apiClient.get<TourResponse[]>('/tours/not_ended');
    },

    async getEnded(startDate?: string, endDate?: string): Promise<TourResponse[]> {
        const params = new URLSearchParams();
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);
        const query = params.toString();
        return apiClient.get<TourResponse[]>(`/tours/ended${query ? `?${query}` : ''}`);
    },

    async getById(tourId: number): Promise<TourResponse> {
        return apiClient.get<TourResponse>(`/tours/${tourId}`);
    },

    async start(data: StartTourRequest): Promise<TourResponse> {
        return apiClient.post<TourResponse>('/tours', data);
    },

    async end(tourId: number, data: EndTourRequest): Promise<TourResponse> {
        return apiClient.put<TourResponse>(`/tours/${tourId}/end`, data);
    },

    async getPlayersPoints(tourId: number): Promise<TourPlayerPointsResponse[]> {
        return apiClient.get<TourPlayerPointsResponse[]>(`/tours/${tourId}/players_points`);
    },
};