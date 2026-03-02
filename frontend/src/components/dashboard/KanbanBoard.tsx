import { useMemo, useState, DragEvent } from 'react';
import { useAppointments, Appointment } from '@/hooks/useAppointments';
import { Card, CardContent } from '@/components/ui/card';
import { format } from 'date-fns';
import AppointmentEditDialog from './AppointmentEditDialog';
import { useQueryClient } from "@tanstack/react-query";
import { useWebSocket } from "@/contexts/WebSocketContext";
import { useEffect } from "react";
import { useUpdateAppointmentStatus } from '@/hooks/useUpdateAppointmentStatus';

const COLUMNS = [
    { id: 'waitlist', title: 'Лист ожидания' },
    { id: 'new', title: 'Новая' },
    { id: 'confirmed', title: 'Подтверждена' },
    { id: 'in_progress', title: 'В работе' },
    { id: 'done', title: 'Готова' },
];

function DraggableCard({ appointment, onEdit, onDragStart }: {
    appointment: Appointment,
    onEdit: (appt: Appointment) => void,
    onDragStart: (e: DragEvent, appointment: Appointment) => void,
}) {
    return (
        <div
            draggable
            onDragStart={(e) => onDragStart(e, appointment)}
            onClick={() => onEdit(appointment)}
            className="mb-3 group relative cursor-pointer active:cursor-grabbing transition-all duration-300"
        >
            <Card className="hover:shadow-xl hover:scale-[1.02] transition-all duration-300 border-l-4 border-l-primary/40 bg-card/60 backdrop-blur-sm overflow-hidden border-border/50">
                <CardContent className="p-4">
                    <div className="flex justify-between items-start mb-1">
                        <div className="text-xs font-bold uppercase tracking-wider text-primary/70">
                            ID #{appointment.id}
                        </div>
                        <div className="text-xs font-mono font-medium text-muted-foreground bg-muted/50 px-2 py-0.5 rounded">
                            {format(new Date(appointment.start_time), 'HH:mm')}
                        </div>
                    </div>

                    <div className="font-bold text-sm text-card-foreground mb-2 line-clamp-2">
                        {appointment.service?.name || "Услуга не указана"}
                    </div>

                    {/* Expandable info on hover */}
                    <div className="space-y-1.5 pt-2 border-t border-border/30 opacity-60 group-hover:opacity-100 transition-opacity duration-300">
                        <div className="flex items-center gap-2 text-[11px] font-medium text-muted-foreground">
                            <span className="shrink-0 text-primary/60 text-xs">👤</span>
                            <span className="truncate">{appointment.client?.full_name || "Без имени"}</span>
                        </div>
                        {(appointment.car_make || appointment.car_year) && (
                            <div className="flex items-center gap-2 text-[11px] font-medium text-muted-foreground">
                                <span className="shrink-0 text-primary/60 text-xs">🚗</span>
                                <span className="truncate">
                                    {appointment.car_make || "Авто"}{appointment.car_year ? `, ${appointment.car_year}` : ""}
                                </span>
                            </div>
                        )}
                        {appointment.notes && (
                            <div className="flex items-start gap-2 text-[11px] font-medium text-muted-foreground italic">
                                <span className="shrink-0 text-primary/60 text-xs">📝</span>
                                <p className="line-clamp-2 leading-snug">{appointment.notes}</p>
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

function DroppableColumn({ id, title, appointments, onEdit, onDragStart, onDrop, isOver }: {
    id: string,
    title: string,
    appointments: Appointment[],
    onEdit: (appt: Appointment) => void,
    onDragStart: (e: DragEvent, appointment: Appointment) => void,
    onDrop: (e: DragEvent, columnId: string) => void,
    isOver: boolean,
}) {
    return (
        <div
            onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
            }}
            onDragEnter={(e) => e.preventDefault()}
            onDrop={(e) => onDrop(e, id)}
            className={`p-4 rounded-xl min-h-[500px] w-full transition-colors duration-200 border border-transparent ${isOver
                ? 'bg-primary/10 ring-2 ring-primary/30 border-primary/20'
                : 'bg-muted/50 hover:bg-muted/80'
                }`}
        >
            <h3 className="font-semibold mb-4 text-foreground flex items-center justify-between">
                {title}
                {appointments.length > 0 && (
                    <span className="ml-2 text-xs font-bold bg-primary/20 text-primary px-2.5 py-0.5 rounded-full">
                        {appointments.length}
                    </span>
                )}
            </h3>
            <div className="space-y-2">
                {appointments.map((appt) => (
                    <DraggableCard
                        key={appt.id}
                        appointment={appt}
                        onEdit={onEdit}
                        onDragStart={onDragStart}
                    />
                ))}
            </div>
        </div>
    );
}

export default function KanbanBoard() {
    const { data: appointments = [] } = useAppointments();
    const queryClient = useQueryClient();
    const { lastMessage } = useWebSocket();
    const updateStatusMutation = useUpdateAppointmentStatus();

    const [selectedAppointment, setSelectedAppointment] = useState<Appointment | null>(null);
    const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
    const [dragOverColumn, setDragOverColumn] = useState<string | null>(null);
    const [draggedAppointment, setDraggedAppointment] = useState<Appointment | null>(null);

    // Listen for real-time updates
    useEffect(() => {
        if (lastMessage) {
            console.log("WS Update received:", lastMessage);
            queryClient.invalidateQueries({ queryKey: ["appointments"] });
        }
    }, [lastMessage, queryClient]);

    // Group appointments by status
    const groupedAppointments = useMemo(() => {
        const groups: Record<string, Appointment[]> = {
            waitlist: [],
            new: [],
            confirmed: [],
            in_progress: [],
            done: [],
            cancelled: []
        };
        appointments.forEach(appt => {
            const status = appt.status.toLowerCase();
            if (groups[status]) {
                groups[status].push(appt);
            }
        });
        return groups;
    }, [appointments]);

    const handleDragStart = (e: DragEvent, appointment: Appointment) => {
        setDraggedAppointment(appointment);
        e.dataTransfer.setData('text/plain', String(appointment.id));
        e.dataTransfer.effectAllowed = 'move';
    };

    const handleDrop = (e: DragEvent, columnId: string) => {
        e.preventDefault();
        setDragOverColumn(null);

        if (!draggedAppointment) return;

        const newStatus = columnId.toUpperCase();
        if (draggedAppointment.status.toUpperCase() !== newStatus) {
            console.log(`Moving ${draggedAppointment.id} to ${newStatus}`);
            updateStatusMutation.mutate(
                { id: draggedAppointment.id, status: newStatus },
                {
                    onError: (error) => {
                        console.error('Failed to update status:', error);
                        alert('Не удалось обновить статус. Проверьте права доступа.');
                    }
                }
            );
        }
        setDraggedAppointment(null);
    };

    const handleEdit = (appt: Appointment) => {
        setSelectedAppointment(appt);
        setIsEditDialogOpen(true);
    };

    return (
        <>
            <div
                className="grid grid-cols-1 md:grid-cols-5 gap-6"
                onDragOver={(e) => {
                    e.preventDefault();
                    // Find which column we're over
                    const target = (e.target as HTMLElement).closest('[data-column-id]');
                    if (target) {
                        setDragOverColumn(target.getAttribute('data-column-id'));
                    }
                }}
                onDragEnd={() => {
                    setDragOverColumn(null);
                    setDraggedAppointment(null);
                }}
            >
                {COLUMNS.map(col => (
                    <div key={col.id} data-column-id={col.id}>
                        <DroppableColumn
                            id={col.id}
                            title={col.title}
                            appointments={groupedAppointments[col.id] || []}
                            onEdit={handleEdit}
                            onDragStart={handleDragStart}
                            onDrop={handleDrop}
                            isOver={dragOverColumn === col.id}
                        />
                    </div>
                ))}
            </div>

            <AppointmentEditDialog
                appointment={selectedAppointment}
                isOpen={isEditDialogOpen}
                onClose={() => setIsEditDialogOpen(false)}
            />
        </>
    );
}
