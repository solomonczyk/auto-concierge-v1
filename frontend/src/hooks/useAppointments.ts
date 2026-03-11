import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface Appointment {
    id: number;
    shop_id: number;
    service_id: number;
    client_id: number;
    start_time: string;
    end_time: string;
    status: "new" | "confirmed" | "in_progress" | "completed" | "cancelled" | "no_show" | "waitlist";
    completed_at?: string | null;
    notes?: string;
    auto_info?: {
        car_make?: string;
        car_year?: number;
        vin?: string;
    };
    client?: {
        id: number;
        full_name: string;
        phone?: string;
        telegram_id?: number;
    };
    service?: {
        id: number;
        name: string;
        duration_minutes: number;
        base_price: number;
    };
}

export function useAppointments(options?: { forKanban?: boolean }) {
    const forKanban = options?.forKanban ?? false
    return useQuery({
        queryKey: ["appointments", forKanban ? "kanban" : "all"],
        queryFn: async () => {
            const params = forKanban ? { for_kanban: "1" } : {}
            const { data } = await api.get("/appointments/", { params })
            return data
        },
    })
}

export function useUpdateAppointmentStatus() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async ({ id, status }: { id: number; status: string }) => {
            return api.patch(`/appointments/${id}/status`, { status });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["appointments"] });
        },
    });
}
