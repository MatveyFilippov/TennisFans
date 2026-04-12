import { playersApi } from '../api/players.js';
import { toursApi } from '../api/tours.js';
import { matchesApi } from '../api/matches.js';
import { PlayerResponse, RegisterMatchRequest, StartTourRequest, CreatePlayerRequest } from '../types/index.js';

export class AdminPanel {
    private adminSection: HTMLElement;
    private adminToggleBtn: HTMLElement;
    private closeAdminBtn: HTMLElement;
    private tournamentSection: HTMLElement;

    // Forms
    private registerMatchForm: HTMLFormElement;
    private createTourForm: HTMLFormElement;
    private addPlayerForm: HTMLFormElement;

    // Selects
    private playerSelects: HTMLSelectElement[] = [];

    // Tabs
    private tabButtons: NodeListOf<Element>;
    private tabContents: NodeListOf<Element>;

    private players: PlayerResponse[] = [];

    constructor() {
        this.adminSection = document.getElementById('adminSection')!;
        this.adminToggleBtn = document.getElementById('adminToggleBtn')!;
        this.closeAdminBtn = document.getElementById('closeAdminBtn')!;
        this.tournamentSection = document.getElementById('tournamentSection')!;

        this.registerMatchForm = document.getElementById('registerMatchForm') as HTMLFormElement;
        this.createTourForm = document.getElementById('createTourForm') as HTMLFormElement;
        this.addPlayerForm = document.getElementById('addPlayerForm') as HTMLFormElement;

        this.tabButtons = document.querySelectorAll('.tab-button');
        this.tabContents = document.querySelectorAll('.tab-content');

        this.init();
    }

    private async init() {
        this.setupEventListeners();
        this.setupTabs();
        await this.loadPlayers();
        this.setupDateTimeDefaults();
    }

    private setupEventListeners() {
        this.adminToggleBtn.addEventListener('click', () => this.toggleAdminPanel());
        this.closeAdminBtn.addEventListener('click', () => this.toggleAdminPanel());

        this.registerMatchForm.addEventListener('submit', (e) => this.handleRegisterMatch(e));
        this.createTourForm.addEventListener('submit', (e) => this.handleCreateTour(e));
        this.addPlayerForm.addEventListener('submit', (e) => this.handleAddPlayer(e));
    }

    private setupTabs() {
        this.tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabName = button.getAttribute('data-tab');
                this.switchTab(tabName!);
            });
        });
    }

    private switchTab(tabName: string) {
        this.tabButtons.forEach(btn => {
            btn.classList.toggle('active', btn.getAttribute('data-tab') === tabName);
        });

        this.tabContents.forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}Tab`);
        });
    }

    private setupDateTimeDefaults() {
        const now = new Date();
        const dateInput = document.getElementById('matchDate') as HTMLInputElement;
        const timeInput = document.getElementById('matchTime') as HTMLInputElement;

        dateInput.value = now.toISOString().split('T')[0];
        timeInput.value = now.toTimeString().slice(0, 5);
    }

    private async loadPlayers() {
        try {
            this.players = await playersApi.getAll();
            this.populatePlayerSelects();
        } catch (error) {
            console.error('Failed to load players:', error);
            this.showNotification('Не удалось загрузить список игроков', 'error');
        }
    }

    private populatePlayerSelects() {
        const selectIds = ['side1Player1', 'side1Player2', 'side2Player1', 'side2Player2'];

        selectIds.forEach(id => {
            const select = document.getElementById(id) as HTMLSelectElement;
            if (select) {
                this.playerSelects.push(select);
                select.innerHTML = '<option value="">Выберите игрока</option>' +
                    this.players.map(player =>
                        `<option value="${player.id}">${this.escapeHtml(player.name)}</option>`
                    ).join('');
            }
        });
    }

    private toggleAdminPanel() {
        this.adminSection.classList.toggle('hidden');
        this.tournamentSection.classList.toggle('hidden');

        if (!this.adminSection.classList.contains('hidden')) {
            this.loadPlayers(); // Refresh player list when opening admin panel
        }
    }

    private async handleRegisterMatch(event: Event) {
        event.preventDefault();

        try {
            const matchData = this.collectMatchData();

            // Validation
            if (!this.validateMatchData(matchData)) {
                return;
            }

            await matchesApi.register(matchData);
            this.showNotification('Матч успешно зарегистрирован!', 'success');
            this.registerMatchForm.reset();
            this.setupDateTimeDefaults();

            // Refresh tournament board if visible
            const event_ = new CustomEvent('matchRegistered');
            window.dispatchEvent(event_);
        } catch (error) {
            console.error('Failed to register match:', error);
            this.showNotification('Не удалось зарегистрировать матч', 'error');
        }
    }

    private collectMatchData(): RegisterMatchRequest {
        const side1Player1 = parseInt((document.getElementById('side1Player1') as HTMLSelectElement).value);
        const side1Player2 = parseInt((document.getElementById('side1Player2') as HTMLSelectElement).value);
        const side1Score = parseInt((document.getElementById('side1Score') as HTMLInputElement).value);

        const side2Player1 = parseInt((document.getElementById('side2Player1') as HTMLSelectElement).value);
        const side2Player2 = parseInt((document.getElementById('side2Player2') as HTMLSelectElement).value);
        const side2Score = parseInt((document.getElementById('side2Score') as HTMLInputElement).value);

        const matchDate = (document.getElementById('matchDate') as HTMLInputElement).value;
        const matchTime = (document.getElementById('matchTime') as HTMLInputElement).value;
        const playedAt = new Date(`${matchDate}T${matchTime}`).toISOString();

        return {
            side1: {
                player1_id: side1Player1,
                player2_id: side1Player2,
                match_score: side1Score
            },
            side2: {
                player1_id: side2Player1,
                player2_id: side2Player2,
                match_score: side2Score
            },
            played_at: playedAt
        };
    }

    private validateMatchData(data: RegisterMatchRequest): boolean {
        const players = [
            data.side1.player1_id, data.side1.player2_id,
            data.side2.player1_id, data.side2.player2_id
        ];

        // Check if all players are selected
        if (players.some(id => !id)) {
            this.showNotification('Выберите всех игроков', 'error');
            return false;
        }

        // Check for duplicate players in same side
        if (data.side1.player1_id === data.side1.player2_id) {
            this.showNotification('Игроки на одной стороне должны быть разными', 'error');
            return false;
        }

        if (data.side2.player1_id === data.side2.player2_id) {
            this.showNotification('Игроки на одной стороне должны быть разными', 'error');
            return false;
        }

        // Check for same player on both sides
        const allPlayerIds = new Set(players);
        if (allPlayerIds.size !== 4) {
            this.showNotification('Один и тот же игрок не может быть на обеих сторонах', 'error');
            return false;
        }

        // Validate scores
        if (isNaN(data.side1.match_score) || data.side1.match_score < 0) {
            this.showNotification('Введите корректный счёт для стороны 1', 'error');
            return false;
        }

        if (isNaN(data.side2.match_score) || data.side2.match_score < 0) {
            this.showNotification('Введите корректный счёт для стороны 2', 'error');
            return false;
        }

        return true;
    }

    private async handleCreateTour(event: Event) {
        event.preventDefault();

        try {
            const tourName = (document.getElementById('tourName') as HTMLInputElement).value.trim();

            if (!tourName) {
                this.showNotification('Введите название тура', 'error');
                return;
            }

            const tourData: StartTourRequest = {
                name: tourName,
                started_at: new Date().toISOString()
            };

            await toursApi.start(tourData);
            this.showNotification('Тур успешно создан!', 'success');
            this.createTourForm.reset();

            // Refresh tournament board
            const event_ = new CustomEvent('tourCreated');
            window.dispatchEvent(event_);
        } catch (error) {
            console.error('Failed to create tour:', error);
            this.showNotification('Не удалось создать тур', 'error');
        }
    }

    private async handleAddPlayer(event: Event) {
        event.preventDefault();

        try {
            const playerName = (document.getElementById('playerName') as HTMLInputElement).value.trim();

            if (!playerName) {
                this.showNotification('Введите имя игрока', 'error');
                return;
            }

            const playerData: CreatePlayerRequest = {
                name: playerName,
                registered_at: new Date().toISOString()
            };

            await playersApi.create(playerData);
            this.showNotification('Игрок успешно добавлен!', 'success');
            this.addPlayerForm.reset();

            // Refresh player list
            await this.loadPlayers();
        } catch (error) {
            console.error('Failed to add player:', error);
            this.showNotification('Не удалось добавить игрока', 'error');
        }
    }

    private showNotification(message: string, type: 'success' | 'error' | 'info' = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 16px 24px;
            background: ${type === 'success' ? 'var(--success-color)' : type === 'error' ? 'var(--accent-color)' : 'var(--secondary-color)'};
            color: white;
            border-radius: 12px;
            box-shadow: var(--shadow-lg);
            z-index: 1000;
            animation: slideIn 0.3s ease;
            backdrop-filter: blur(10px);
            background: ${type === 'success' ? 'rgba(39, 174, 96, 0.9)' : type === 'error' ? 'rgba(231, 76, 60, 0.9)' : 'rgba(52, 152, 219, 0.9)'};
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    private escapeHtml(text: string): string {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);