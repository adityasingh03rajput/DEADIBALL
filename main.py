import java.util.HashMap;

public class hasmap3 {
    public static void main(String[] args) {
        String str="programming";
        char[]ch=str.toCharArray();
        HashMap<Character, Integer> ma=new HashMap<>();
        for (char i:ch)
        {
            ma.put(i, ma.getOrDefault(i,0)+1);

        }
        System.out.println(ma);

    }
