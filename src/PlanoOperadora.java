public class PlanoOperadora {
    public static void main(String[] args) {
        String plano = "M"; //M /T 

        if (plano.equals("M")) {
            System.out.println("Plano Master R$ 120,00");
        } else if (plano.equals("T")) {
            System.out.println("Plano Top R$ 99,00");
        } else {
            System.out.println("Plano não existente");
        }
    }
}
