import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface UpdateAppointmentData {
    id: number;
    service_id?: number;
    start_time?: string;
    car_make?: string | null;
    car_year?: number | null;
    vin?: string | null;
}

export function useUpdateAppointment() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async ({ id, ...data }: UpdateAppointmentData) => {
            const response = await api.patch(`/appointments/${id}`, data);
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["appointments"] });
        },
    });
}
