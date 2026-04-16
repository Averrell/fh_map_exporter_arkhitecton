using System;

namespace Exporter
{
    internal static class TransformMath
    {
        /// <summary>YPR rotation matrix (UE convention). Input in degrees.</summary>
        public static double[,] RotationMatrix(double pitch, double yaw, double roll)
        {
            double pitchRad = pitch * Math.PI / 180.0;
            double yawRad   = yaw   * Math.PI / 180.0;
            double rollRad  = roll  * Math.PI / 180.0;

            double cy = Math.Cos(yawRad),   sy = Math.Sin(yawRad);
            double cp = Math.Cos(pitchRad), sp = Math.Sin(pitchRad);
            double cr = Math.Cos(rollRad),  sr = Math.Sin(rollRad);

            return new double[3, 3]
            {
                {  cp*cy,   sr*sp*cy - cr*sy,  -(cr*sp*cy + sr*sy) },
                {  cp*sy,   sr*sp*sy + cr*cy,    sr*cy - cr*sp*sy  },
                {  sp,     -sr*cp,               cr*cp             },
            };
        }

        public static double[,] QuaternionToMatrix(double qx, double qy, double qz, double qw)
        {
            return new double[3, 3]
            {
                { 1 - 2*(qy*qy + qz*qz), 2*(qx*qy - qz*qw), 2*(qx*qz + qy*qw) },
                { 2*(qx*qy + qz*qw), 1 - 2*(qx*qx + qz*qz), 2*(qy*qz - qx*qw) },
                { 2*(qx*qz - qy*qw), 2*(qy*qz + qx*qw), 1 - 2*(qx*qx + qy*qy) },
            };
        }

        /// <summary>Rotation matrix → (pitch, yaw, roll) in degrees, rounded to 2 dp.</summary>
        public static (double pitch, double yaw, double roll) MatrixToEuler(double[,] R)
        {
            double pitch = Math.Asin(Math.Max(-1.0, Math.Min(1.0,  R[2, 0]))) * 180.0 / Math.PI;
            double yaw   = Math.Atan2(R[1, 0], R[0, 0]) * 180.0 / Math.PI;
            double roll  = Math.Atan2(-R[2, 1], R[2, 2]) * 180.0 / Math.PI;
            return (Math.Round(pitch, 2), Math.Round(yaw, 2), Math.Round(roll, 2));
        }

        public static double[,] MatMul(double[,] A, double[,] B)
        {
            var C = new double[3, 3];
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 3; j++)
                    for (int k = 0; k < 3; k++)
                        C[i, j] += A[i, k] * B[k, j];
            return C;
        }

        public static double[] MatVecMul(double[,] R, double[] v)
        {
            return new double[]
            {
                R[0, 0]*v[0] + R[0, 1]*v[1] + R[0, 2]*v[2],
                R[1, 0]*v[0] + R[1, 1]*v[1] + R[1, 2]*v[2],
                R[2, 0]*v[0] + R[2, 1]*v[1] + R[2, 2]*v[2],
            };
        }

        /// <summary>Produces [x, y, z, sx, sy, sz, pitch, yaw, roll] – canonical 9-element transform entry.</summary>
        public static double[] MakeEntry(double[] pos, double[] scale, double[,] rotMat)
        {
            var (pitch, yaw, roll) = MatrixToEuler(rotMat);
            return new double[]
            {
                Math.Round(pos[0],   2),
                Math.Round(pos[1],   2),
                Math.Round(pos[2],   2),
                Math.Round(scale[0], 2),
                Math.Round(scale[1], 2),
                Math.Round(scale[2], 2),
                pitch, yaw, roll,
            };
        }

        public static double[,] Identity3x3 => new double[3, 3]
        {
            { 1, 0, 0 },
            { 0, 1, 0 },
            { 0, 0, 1 },
        };
    }
}
